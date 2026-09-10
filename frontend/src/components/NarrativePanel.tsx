import { timestamp } from "../format";
import type { Chapter } from "../types";
import Icon from "../ui/Icon";

interface Props {
  summary: string | null;
  chapters: Chapter[];
  keywords: string[];
}

/** What the run said about the source video, rather than about its clips.
 *
 *  Shared by the generate flow and the run detail page because it is the same
 *  three fields in both, read for the same reason: the clips say which moments
 *  were picked, and nothing until now said what the video was.
 *
 *  Renders nothing at all when the run carries no narrative -- a run from before
 *  this existed, or one where the model returned moments and no summary. An
 *  empty card headed "About this video" says less than no card.
 */
export default function NarrativePanel({ summary, chapters, keywords }: Props) {
  if (!summary && chapters.length === 0 && keywords.length === 0) return null;

  return (
    <section className="card" id="narrative">
      <div className="card-header">
        <span className="icon-tile">
          <Icon name="layers" size={15} strokeWidth={2.2} />
        </span>
        <h2>About this video</h2>
      </div>

      {summary && <p className="narrative-summary">{summary}</p>}

      {keywords.length > 0 && (
        <div className="narrative-keywords">
          {keywords.map((keyword) => (
            <span key={keyword} className="badge">
              {keyword}
            </span>
          ))}
        </div>
      )}

      {chapters.length > 0 && (
        <ol className="chapter-list">
          {chapters.map((chapter) => (
            // Start time is the key: two sections can share a title, and no
            // two can start at the same second after validation orders them.
            <li key={chapter.start_seconds} className="chapter">
              <span className="chapter-time o-num">
                {timestamp(chapter.start_seconds)}
              </span>
              <span className="chapter-title">{chapter.title}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
