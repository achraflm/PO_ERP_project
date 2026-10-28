import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { AccessDenied } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import { useSession } from "@/lib/erp/session";
import { readApiError } from "@/lib/erp/api";
import { readSimulationApi, type SavedSimulation } from "@/lib/erp/simulationApi";
import { fmtDateTime } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";
export const Route = createFileRoute("/simulations/")({
  head: () => ({ meta: [{ title: pageTitle("Simulations") }] }),
  component: SimulationList,
});
function SimulationList() {
  const { can } = useSession();
  const query = useQuery({
    queryKey: ["saved-simulations"],
    queryFn: ({ signal }) =>
      readSimulationApi<{ items: SavedSimulation[] }>("/simulations", signal),
    enabled: can("simulation.view"),
    refetchInterval: 15000,
  });
  if (!can("simulation.view")) return <AccessDenied what="simulations" />;
  const columns: Column<SavedSimulation>[] = [
    {
      key: "id",
      header: "Simulation",
      cell: (s) => (
        <Link
          className="text-info underline"
          to="/simulations/$simId"
          params={{ simId: String(s.simulation_id) }}
        >
          #{s.simulation_id}
        </Link>
      ),
    },
    { key: "created", header: "Saved", cell: (s) => fmtDateTime(s.created_at) },
    { key: "target", header: "Target date", cell: (s) => s.target_date },
    {
      key: "pos",
      header: "Purchase orders",
      cell: (s) => [...new Set(s.fgpns.map((f) => f.po_number))].join(", "),
    },
    {
      key: "feasible",
      header: "Feasibility",
      cell: (s) => (s.is_feasible ? "Feasible" : "Shortfall"),
    },
    { key: "allocations", header: "Stock allocations", cell: (s) => s.allocations.length },
  ];
  return (
    <>
      <PageHeader
        title="Saved simulations"
        subtitle="Simulations and stock allocations stored in the database."
        actions={
          can("simulation.run") ? (
            <Button asChild>
              <Link to="/simulations/new">New simulation</Link>
            </Button>
          ) : undefined
        }
      />
      <div className="p-4">
        <div className="panel">
          <DataTable
            rows={query.data?.items ?? []}
            columns={columns}
            rowKey={(s) => String(s.simulation_id)}
            emptyTitle={
              query.isPending
                ? "Loading simulations…"
                : query.isError
                  ? "Could not load simulations"
                  : "No saved simulations"
            }
          />
        </div>
        {query.isError && (
          <p role="alert">{readApiError(query.error, "Could not load simulations.")}</p>
        )}
      </div>
    </>
  );
}
