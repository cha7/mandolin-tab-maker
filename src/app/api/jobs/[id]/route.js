import { SONG_ID, jobs } from "@/data/jobs";
import { localOnly } from "@/lib/local";

// A song's progress, and once done its report and tab.
export async function GET(request, { params }) {
  const refused = localOnly(request);
  if (refused) return refused;
  const { id } = await params;
  if (!SONG_ID.test(id)) return Response.json({ error: "not found" }, { status: 404 });
  return Response.json(jobs.status(id));
}
