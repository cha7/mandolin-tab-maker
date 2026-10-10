import { jobs } from "@/data/jobs";
import { localOnly } from "@/lib/local";

// A song's tab.txt, tab.musicxml, preview.wav or report.json (nothing else).
export async function GET(request, { params }) {
  const refused = localOnly(request);
  if (refused) return refused;
  const { id, file } = await params;
  const f = jobs.file(id, file);
  if (!f) return Response.json({ error: "not found" }, { status: 404 });
  return new Response(f.body, { headers: { "Content-Type": f.type, "Cache-Control": "no-store" } });
}
