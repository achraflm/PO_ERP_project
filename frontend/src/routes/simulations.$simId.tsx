import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { AccessDenied } from "@/components/erp/EmptyState";
import { useSession } from "@/lib/erp/session";
import { readApiError } from "@/lib/erp/api";
import { readSimulationApi, type SavedSimulation } from "@/lib/erp/simulationApi";
import { pageTitle } from "@/lib/erp/appInfo";
export const Route = createFileRoute("/simulations/$simId")({
  head: () => ({ meta: [{ title: pageTitle("Saved simulation") }] }),
  component: SavedSimulationPage,
});
function SavedSimulationPage() {
  const { simId } = Route.useParams();
  const { can } = useSession();
  const query = useQuery({
    queryKey: ["saved-simulations", simId],
    queryFn: ({ signal }) =>
      readSimulationApi<SavedSimulation>(`/simulations/${encodeURIComponent(simId)}`, signal),
    enabled: can("simulation.view"),
  });
  if (!can("simulation.view")) return <AccessDenied what="simulations" />;
  const data = query.data;
  return (
    <>
      <PageHeader
        title={`Simulation #${simId}`}
        subtitle="Saved database allocations. Stock availability is checked again at launch."
        crumbs={[{ label: "Simulations", to: "/simulations" }]}
      />
      <div className="space-y-4 p-4">
        {query.isPending && <p>Loading…</p>}
        {query.isError && (
          <p role="alert">{readApiError(query.error, "Could not load simulation.")}</p>
        )}
        {data && (
          <>
            <p>
              Target: {data.target_date} · {data.is_feasible ? "Feasible" : "Shortfall"} · Safety
              coefficient: {data.safety_coefficient} · Meeting document #
              {data.mtg_minutes_document_id}
            </p>
            <Section title="Saved production quantities">
              <div className="p-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th>PO</th>
                      <th>FGPN</th>
                      <th>Requested</th>
                      <th>Launchable</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.fgpns.map((row, i) => (
                      <tr key={i}>
                        <td>{row.po_number}</td>
                        <td>{row.fgpn_code}</td>
                        <td>{row.quantity}</td>
                        <td>{row.launchable_quantity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
            <Section title="Saved stock allocations">
              <div className="p-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th>Stock unit</th>
                      <th>Source</th>
                      <th>Quantity</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.allocations.map((row, i) => (
                      <tr key={i}>
                        <td>#{row.stock_unit_id}</td>
                        <td>{row.source}</td>
                        <td>{row.quantity}</td>
                        <td>{row.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data.allocations.length === 0 && <p>No physical stock allocations.</p>}
              </div>
            </Section>
          </>
        )}
        <Link to="/simulations" className="text-info underline">
          Back to saved simulations
        </Link>
      </div>
    </>
  );
}
