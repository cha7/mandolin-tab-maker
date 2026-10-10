import { InputError, jobs } from "@/data/jobs";
import { localOnly } from "@/lib/local";

// Starts a tab: { url, options, rerun } -> 202 { song_id }.
export async function POST(request) {
  const refused = localOnly(request);
  if (refused) return refused;
  // JSON only: a form post from another page can't send this type without a preflight.
  if (!(request.headers.get("content-type") ?? "").startsWith("application/json")) {
    return Response.json({ error: "expected JSON" }, { status: 415 });
  }
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "bad JSON" }, { status: 400 });
  }
  try {
    const id = jobs.submit({ url: body?.url, options: body?.options, rerun: Boolean(body?.rerun) });
    return Response.json({ song_id: id }, { status: 202 });
  } catch (e) {
    if (e instanceof InputError) return Response.json({ error: e.message }, { status: 400 });
    throw e;
  }
}
