import { useCallback, useEffect, useState } from "react";
import { ArrowRight, GitMerge, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import api, { getErrorMessageHe } from "../api/client";
import { showToast } from "../components/Toast";
import { IOSButton } from "../components/ui/IOSButton";
import { springSnappy, tapScale } from "@/lib/motion";
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
      className="mx-3 mb-4 rounded-ios-lg border border-separator/40 bg-surface p-4 shadow-ios-sm"
      dir="rtl"
    >
      <h2 className="mb-2 text-headline text-label">{group.canonical}</h2>
      <p className="mb-3 text-subhead text-label-secondary/80">
        בחר את הפריט שיישאר. השאר יאוחדו אליו.
      </p>
      <div className="space-y-1">
        {group.items.map((item) => (
          <label
            key={item.id}
            className="flex cursor-pointer items-center gap-3 rounded-ios-sm p-2 transition-colors hover:bg-fill/5"
          >
            <input
              type="radio"
              name={`target-${group.canonical}`}
              value={item.id}
              checked={targetId === item.id}
              onChange={() => setTargetId(item.id)}
              className="h-4 w-4 accent-brand"
              disabled={merging}
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-callout font-medium text-label">
                {item.name}
              </div>
              {item.note && (
                <div className="truncate text-caption1 text-label-tertiary/80">
                  {item.note}
                </div>
              )}
            </div>
            {item.status === "completed" && (
              <span className="rounded-full bg-fill/15 px-2 py-0.5 text-caption1 text-label-secondary">
                הושלם
              </span>
            )}
          </label>
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        <IOSButton
          variant="filled"
          size="md"
          onClick={handleMerge}
          disabled={merging || !targetId}
          className="flex-1"
        >
          {merging ? "מאחד..." : "אחד פריטים אלה"}
        </IOSButton>
        <IOSButton
          variant="plain"
          size="md"
          onClick={() => onDismissed(group.canonical)}
          disabled={merging}
        >
          התעלם
        </IOSButton>
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
        showToast(
          `${merged_count} פריטים אוחדו ב-${group_count} קבוצות`,
          "success",
        );
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
        <motion.button
          type="button"
          onClick={() => navigate("/list")}
          whileTap={tapScale}
          transition={springSnappy}
          className="rounded-ios-sm p-1.5 text-label-tertiary transition-colors hover:bg-fill/15 hover:text-label-secondary"
          aria-label="חזרה לרשימה"
        >
          <ArrowRight className="h-5 w-5" />
        </motion.button>
        <h1 className="text-title1 text-label">איחוד פריטים כפולים</h1>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="flex justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-fill/30 border-t-brand" />
        </div>
      )}

      {/* Empty state */}
      {!loading && visibleGroups.length === 0 && (
        <div className="px-5 pt-12 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand/15">
            <GitMerge className="h-8 w-8 text-brand" />
          </div>
          <p className="text-headline text-label">אין כפילויות ברשימה שלך</p>
          <p className="mt-1 text-subhead text-label-secondary/80">
            המערכת מאחדת אוטומטית פריטים דומים בקבלות חדשות
          </p>
        </div>
      )}

      {/* Group cards */}
      {!loading && visibleGroups.length > 0 && (
        <>
          <p className="mb-3 px-5 text-subhead text-label-secondary/80">
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

      {/* Auto-merge footer — purple represents AI-driven action */}
      {!loading && visibleGroups.length > 0 && (
        <div className="fixed inset-x-0 bottom-16 z-20 mx-auto max-w-[430px] px-5">
          <motion.button
            type="button"
            onClick={handleAutoMerge}
            disabled={autoMerging}
            whileTap={tapScale}
            transition={springSnappy}
            className="flex w-full items-center justify-center gap-2 rounded-ios-lg bg-accent-purple py-3 text-subhead font-semibold text-white shadow-ios-lg transition-colors hover:bg-accent-purple/90 disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" />
            {autoMerging ? "מאחד..." : "איחוד אוטומטי של כל הקבוצות הבטוחות"}
          </motion.button>
        </div>
      )}
    </div>
  );
}
