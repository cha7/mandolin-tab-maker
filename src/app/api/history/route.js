import { jobs } from "@/data/jobs";
import { localOnly } from "@/lib/local";

// Songs made before, newest first.
export async function GET(request) {
  return localOnly(request) ?? Response.json(jobs.history());
}
