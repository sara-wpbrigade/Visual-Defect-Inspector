/** Compact strip of the latest inspections on the inspection tab. */

import { useEffect, useState } from 'react';

import { ACTION_LABELS, VERDICT, VERDICT_LABELS } from '../constants';
import { relativeTime } from '../lib/format';
import { getInspections } from '../services/api';

const RECENT_LIMIT = 6;

/** Fetch and show the newest inspections as quick-open cards. */
export function RecentInspections({ refreshKey = 0, onSelectInspection, onViewAll }) {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        const data = await getInspections({ limit: RECENT_LIMIT, offset: 0 });
        if (!ignore) {
          setItems(data.items);
          setError(null);
          setStatus('ready');
        }
      } catch (err) {
        if (!ignore) {
          setError(err?.message || 'Could not load recent inspections.');
          setStatus('error');
        }
      }
    }

    load();
    return () => {
      ignore = true;
    };
  }, [refreshKey]);

  return (
    <section className="recent-strip" aria-labelledby="recent-title">
      <div className="recent-strip-header">
        <div>
          <p className="step-label">Latest activity</p>
          <h2 id="recent-title">Recent inspections</h2>
        </div>
        {onViewAll && (
          <button type="button" className="button secondary button-small" onClick={onViewAll}>
            View all
          </button>
        )}
      </div>

      {status === 'error' && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      {status === 'loading' && items.length === 0 && (
        <div className="recent-list" aria-hidden="true">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="recent-card recent-card-skeleton">
              <div className="skeleton-box" style={{ width: 46, height: 46 }} />
              <div className="skeleton-line" style={{ width: '60%', height: 12 }} />
              <div className="skeleton-line" style={{ width: '35%', height: 10 }} />
            </div>
          ))}
        </div>
      )}

      {status === 'ready' && items.length === 0 && (
        <p className="recent-empty">No inspections yet. Run your first inspection above.</p>
      )}

      {items.length > 0 && (
        <div className="recent-list">
          {items.map((item) => {
            const tone = item.verdict === VERDICT.DEFECT ? 'defect' : 'pass';
            const verdict = VERDICT_LABELS[item.verdict] ?? item.verdict;
            const action = ACTION_LABELS[item.action] ?? item.action;
            return (
              <button
                key={item.id}
                type="button"
                className={`recent-card recent-card-${tone}`}
                onClick={() => onSelectInspection?.(item.id)}
              >
                {item.thumbnailUrl ? (
                  <img
                    className="recent-thumb"
                    src={item.thumbnailUrl}
                    alt={`Thumbnail for inspection ${item.id}`}
                    loading="lazy"
                  />
                ) : (
                  <span className="recent-thumb recent-thumb-empty" aria-hidden="true" />
                )}
                <span className="recent-card-body">
                  <span className={`verdict verdict-${tone}`}>{verdict}</span>
                  <span className="recent-category">{item.category ?? 'unknown'}</span>
                  <span className="recent-meta">
                    {action} · {relativeTime(item.createdAt) || '—'}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
