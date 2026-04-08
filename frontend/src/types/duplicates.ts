import type { ListItemData } from "../components/ShoppingList";

export interface DuplicateGroup {
  canonical: string;
  items: ListItemData[];
}

export interface DuplicatesResponse {
  groups: DuplicateGroup[];
}

export interface MergeRequest {
  target_id: string;
  source_ids: string[];
}

export interface AutoMergeResponse {
  merged_count: number;
  group_count: number;
}
