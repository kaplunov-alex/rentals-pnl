interface Props {
  value: string | null
  properties: string[]
  onChange: (value: string) => void
  disabled?: boolean
}

export default function PropertySelect({ value, properties, onChange, disabled }: Props) {
  return (
    <select
      value={value ?? ''}
      onChange={e => onChange(e.target.value)}
      disabled={disabled}
      className="w-full text-sm border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
    >
      <option value="">-- property --</option>
      {properties.map(p => (
        <option key={p} value={p}>{p}</option>
      ))}
    </select>
  )
}
