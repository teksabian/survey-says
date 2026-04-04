export default function ConnectionDot({ connected }) {
  return (
    <div
      className={`connection-status${connected ? '' : ' disconnected'}`}
      title={connected ? 'Connected' : 'Disconnected'}
    />
  )
}
