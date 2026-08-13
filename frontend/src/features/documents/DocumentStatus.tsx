import type { DocumentStatus as Status } from "../../api/contracts";

const statusLabels: Record<Status, string> = {
  uploaded: "等待处理",
  processing: "处理中",
  ready: "可用",
  failed: "处理失败",
};

export function DocumentStatus({ status }: { status: Status }) {
  return <span className={`document-status status-${status}`}>{statusLabels[status]}</span>;
}
