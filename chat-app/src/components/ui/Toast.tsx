export function Toast({ message }: { message: string | null }) {
  return <div className={`toast${message ? ' on' : ''}`}>{message}</div>;
}
