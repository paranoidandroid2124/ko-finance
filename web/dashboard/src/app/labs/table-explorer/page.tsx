import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableExplorerView } from "@/components/table-explorer/TableExplorerView";

export default function TableExplorerLabPage() {
  if (process.env.NEXT_PUBLIC_ENABLE_LABS !== "true") {
    return (
      <AppShell>
        <EmptyState
          title="Labs 기능이 비활성화되었습니다"
          description="환경 변수 NEXT_PUBLIC_ENABLE_LABS=true 로 설정하면 Table Explorer를 체험할 수 있습니다."
        />
      </AppShell>
    );
  }

  return <TableExplorerView />;
}
