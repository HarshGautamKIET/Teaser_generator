"""The Gemini stage: what it reports, when it stops, and how many run at once.

Written after the runs of 2026-08-24. Four jobs entered this stage within
twenty-six minutes of each other, each uploading its source over the same
uplink at roughly 68 KB/s, all four sat at 25% for half an hour, and all four
died together when the connections dropped. Two of them had been cancelled
twelve minutes earlier and were still transferring.

Nothing here needs a network: the stage's contract with the provider is a
progress callback, so a stub can exercise every path the real upload takes.
"""

import threading
import time

from app.database import user_session
from app.models import Job, JobStatus, Teaser
from tests.conftest import OWNER_ID, requires_ffmpeg
from tests.test_cancel import cancel_out_of_band, job_status, queue_job
from tests.test_generation import StubProvider, good_candidates, run


def job_row(job_id):
    """Read the job the way the polling frontend does -- from its own session,
    so only what the worker has committed is visible."""
    with user_session(OWNER_ID) as db:
        job = db.get(Job, job_id)
        return job.progress, job.message


class ReportingProvider(StubProvider):
    """Reports a transfer the way GeminiProvider does, without one.

    `steps` is a list of (sent, total) pairs, so a test can describe the exact
    transfer it wants to observe rather than a byte count it has to work out.
    """

    def __init__(self, steps, candidates=None, between=None):
        super().__init__(candidates)
        self._steps = steps
        self._between = between
        self.reported = []

    def analyze_video(self, request):
        for sent, total in self._steps:
            request.on_progress(sent, total)
            self.reported.append(job_row(request_job_id(request)))
            if self._between is not None:
                self._between()
        return super().analyze_video(request)


# The stub needs to read back the row the callback just wrote, and the request
# carries no job id -- it deliberately describes the video, not the run. The
# tests pass the id in through a closure instead; this indirection exists only
# so ReportingProvider can be shared between them.
_current_job_id = threading.local()


def request_job_id(request):
    return _current_job_id.value


def watching(job_id):
    _current_job_id.value = job_id


# ----------------------------------------------------------------------
# Progress
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_upload_progress_moves_the_job_past_25(client, uploaded_video):
    """25% used to cover the upload, the wait for Gemini to process the file and
    the analysis itself. A 173 MB source held it there for half an hour with no
    way to tell a slow transfer from a hung one."""
    job_id = queue_job(client, uploaded_video["video_id"])
    watching(job_id)
    provider = ReportingProvider([(25, 100), (50, 100), (75, 100)], good_candidates())

    run(job_id, provider)

    assert [progress for progress, _ in provider.reported] == [30, 35, 40]
    assert all("MB" in message for _, message in provider.reported)


@requires_ffmpeg
def test_a_finished_upload_hands_over_to_the_analysis(client, uploaded_video):
    """The last byte sent is not the end of the stage -- the model has still to
    watch the video. The message says which of the two is happening."""
    job_id = queue_job(client, uploaded_video["video_id"])
    watching(job_id)
    provider = ReportingProvider([(100, 100)], good_candidates())

    run(job_id, provider)

    assert provider.reported == [(45, "Finding strong moments")]


@requires_ffmpeg
def test_a_provider_that_reports_nothing_still_runs(client, uploaded_video):
    """The callback is a courtesy, not a protocol. `fake`, and every stub in
    this suite, never calls it."""
    job_id = queue_job(client, uploaded_video["video_id"])

    job = run(job_id, StubProvider(good_candidates()))

    assert job.status == JobStatus.COMPLETED


# ----------------------------------------------------------------------
# Stopping a transfer
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_cancel_during_the_upload_stops_the_transfer(client, uploaded_video):
    """Cancellation used to land only at a stage boundary, which for this stage
    meant after the upload finished. On 2026-08-24 that was twelve minutes of
    bandwidth spent on two runs nobody was waiting for -- taken from the two
    that were still live."""
    job_id = queue_job(client, uploaded_video["video_id"])
    watching(job_id)
    kept_going = []

    class CancelsMidTransfer(ReportingProvider):
        def analyze_video(self, request):
            request.on_progress(10, 100)
            cancel_out_of_band(job_id)
            request.on_progress(20, 100)      # the row is gone; this must raise
            kept_going.append(True)
            return StubProvider.analyze_video(self, request)

    run(job_id, CancelsMidTransfer([], good_candidates()))

    assert kept_going == [], "the transfer continued past the cancellation"
    assert job_status(job_id) == JobStatus.CANCELLED
    with user_session(OWNER_ID) as db:
        assert db.query(Teaser).filter(Teaser.job_id == job_id).count() == 0


# ----------------------------------------------------------------------
# One at a time
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_only_one_run_holds_the_analysis_stage(client, uploaded_video):
    """Concurrent uploads do not finish sooner than sequential ones on a single
    uplink; they finish later, or not at all."""
    video_id = uploaded_video["video_id"]
    jobs = [queue_job(client, video_id), queue_job(client, video_id)]
    inside = []
    peak = []

    class Slow(StubProvider):
        def analyze_video(self, request):
            inside.append(1)
            peak.append(len(inside))
            time.sleep(0.3)
            inside.pop()
            return super().analyze_video(request)

    threads = [
        threading.Thread(target=run, args=(job_id, Slow(good_candidates())))
        for job_id in jobs
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert peak == [1, 1], f"two runs were inside the stage at once: {peak}"


@requires_ffmpeg
def test_a_run_that_waits_for_the_slot_says_so(client, uploaded_video):
    """A run queued behind another is not stuck, and the message is the only
    place that difference can be seen."""
    video_id = uploaded_video["video_id"]
    first, second = queue_job(client, video_id), queue_job(client, video_id)
    holding = threading.Event()
    release = threading.Event()
    waiting_message = []

    class Holds(StubProvider):
        def analyze_video(self, request):
            holding.set()
            release.wait(timeout=10)
            return super().analyze_video(request)

    blocker = threading.Thread(target=run, args=(first, Holds(good_candidates())))
    blocker.start()
    assert holding.wait(timeout=10), "the first run never reached the stage"

    queued = threading.Thread(target=run, args=(second, StubProvider(good_candidates())))
    queued.start()
    # Give the second run time to reach the slot and find it taken.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        _, message = job_row(second)
        if "aiting" in message:
            waiting_message.append(message)
            break
        time.sleep(0.05)

    release.set()
    blocker.join(timeout=30)
    queued.join(timeout=30)

    assert waiting_message, "the queued run never said it was waiting"
