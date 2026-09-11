/**
 * A `refetchInterval` that keeps polling only while the data still says "not finished"
 * — documents that are pending/processing, jobs that are queued/running. Returns false
 * once the predicate stops holding, so a settled query goes quiet.
 */
export function pollWhile<TData>(
  predicate: (data: TData) => boolean,
  intervalMs: number
): (query: { state: { data: TData | undefined } }) => number | false {
  return (query) => (query.state.data !== undefined && predicate(query.state.data) ? intervalMs : false);
}
