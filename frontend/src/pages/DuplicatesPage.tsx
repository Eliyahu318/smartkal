import { useCallback, useEffect, useState } from "react";
import { ArrowRight, GitMerge, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import api, { getErrorMessageHe } from "../api/client";
import { showToast } from "../components/Toast";
import type {
  AutoMergeResponse,
  DuplicateGroup,
  DuplicatesResponse,
} from "../types/duplicates";

interface GroupCardProps {
  group: DuplicateGroup;
  onMerged: () => void;
  onDismissed: (canonical: string) => void;
}

function GroupCard({ group, onMerged, onDismissed }: GroupCardProps) {
  // Default target = oldest item (first in the array, since backend orders by created_at)
  const [targetId, setTargetId] = useState<string>(group.items[0]?.id ?? "");
  const [merging, setMerging] = useState(false);

  const handleMerge = useCallback(async () => {
    if (!targetId || merging) return;
    setMerging(true);
    try {
      const sourceIds = group.items
        .filter((i) => i.id !== targetId)
        .map((i) => i.id);
      await api.post("/api/v1/list/merge", {
        target_id: targetId,
        source_ids: sourceIds,
      });
      showToast("הפריטים אוחדו בהצלחה", "success");
      onMerged();
    } catch (err) {
      showToast(getErrorMessageHe(err));
    } finally {
      setMerging(false);
    }
  }, [targetId, merging, group.items, onMerged]);

  return (
    <div
      className="mx-5 mb-4 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm"
      dir="rtl"
    >
      <h2 className="mb-3 text-lg font-bold text-gray-900">{group.canonical}</h2>
      <p className="mb-3 text-sm text-gray-500">
        בחר את הפריט שיישאר. השאר יאוחדו אליו.
      </p>
      <div className="space-y-2">
        {group.items.map((item) => (
          <label
            key={item.id}
            className="flex cursor-pointer items-center gap-3 rounded-lg p-2 hover:bg-gray-50"
          >
            <input
              type="radio"
              name={`target-${group.canonical}`}
              value={item.id}
              checked={targetId === item.id}
              onChange={() => setTargetId(item.id)}
              className="h-4 w-4 accent-green-600"
              disabled={merging}
            />
            <div className="flex-1 min-w-0">
              <div className="truncate text-sm font-medium text-gray-900">
                {item.name}
              </div>
              {item.note && (
                <div className="truncate text-xs text-gray-500">{item.note}</div>
              )}
            </div>
            {item.status === "completed" && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                הושלם
              </span>
            )}
          </label>
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={handleMerge}
          disabled={merging || !targetId}
          className="flex-1 rounded-xl bg-green-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-green-700 disabled:opacity-50"
        >
          {merging ? "מאחד..." : "אחד פריטים אלה"}
        </button>
        <button
          type="button"
          onClick={() => onDismissed(group.canonical)}
          disabled={merging}
          className="rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-600 transition hover:bg-gray-50 disabled:opacity-50"
        >
          התעלם
        </button>
      </div>
    </div>
  );
}

export function DuplicatesPage() {
  const navigate = useNavigate();
  const [groups, setGroups] = useState<DuplicateGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoMerging, setAutoMerging] = useState(false);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const fetchGroups = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await api.get<DuplicatesResponse>("/api/v1/list/duplicates", {
        signal,
      });
      setGroups(res.data.groups);
    } catch (err) {
      if (signal?.aborted) return;
      showToast(getErrorMessageHe(err));
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void fetchGroups(controller.signal);
    return () => controller.abort();
  }, [fetchGroups]);

  const handleAutoMerge = useCallback(async () => {
    if (autoMerging) return;
    setAutoMerging(true);
    try {
      const res = await api.post<AutoMergeResponse>(
        "/api/v1/list/duplicates/auto-merge",
      );
      const { merged_count, group_count } = res.data;
      if (merged_count > 0) {
        showToast(`${merged_count} פריטים אוחדו ב-${group_count} קבוצות`, "success");
      } else {
        showToast("לא נמצאו קבוצות בטוחות לאיחוד אוטומטי", "info");
      }
      await fetchGroups();
    } catch (err) {
      showToast(getErrorMessageHe(err));
    } finally {
      setAutoMerging(false);
    }
  }, [autoMerging, fetchGroups]);

  const handleGroupMerged = useCallback(() => {
    void fetchGroups();
  }, [fetchGroups]);

  const handleDismiss = useCallback((canonical: string) => {
    setDismissed((prev) => {
      const next = new Set(prev);
      next.add(canonical);
      return next;
    });
  }, []);

  const visibleGroups = groups.filter((g) => !dismissed.has(g.canonical));

  return (
    <div className="pt-14 pb-24" dir="rtl">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 pb-4">
        <button
          type="button"
          onClick={() => navigate("/list")}
          className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100"
          aria-label="חזרה לרשימה"
        >
          <ArrowRight className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-bold">איחוד פריטים כפולים</h1>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="flex justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-green-500" />
        </div>
      )}

      {/* Empty state */}
      {!loading && visibleGroups.length === 0 && (
        <div className="px-5 pt-12 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-50">
            <GitMerge className="h-8 w-8 text-green-600" />
          </div>
          <p className="text-base font-medium text-gray-900">
            אין כפילויות ברשימה שלך
          </p>
          <p className="mt-1 text-sm text-gray-500">
            המערכת מאחדת אוטומטית פריטים דומים בקבלות חדשות
          </p>
        </div>
      )}

      {/* Group cards */}
      {!loading && visibleGroups.length > 0 && (
        <>
          <p className="mb-3 px-5 text-sm text-gray-500">
            נמצאו {visibleGroups.length} קבוצות של פריטים דומים
          </p>
          {visibleGroups.map((group) => (
            <GroupCard
              key={group.canonical}
              group={group}
              onMerged={handleGroupMerged}
              onDismissed={handleDismiss}
            />
          ))}
        </>
      )}

      {/* Auto-merge footer */}
      {!loading && visibleGroups.length > 0 && (
        <div className="fixed inset-x-0 bottom-16 z-20 mx-auto max-w-[430px] px-5">
          <button
            type="button"
            onClick={handleAutoMerge}
            disabled={autoMerging}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-purple-600 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-purple-700 disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" />
            {autoMerging ? "מאחד..." : "איחוד אוטומטי של כל הקבוצות הבטוחות"}
          </button>
        </div>
      )}
    </div>
  );
}
