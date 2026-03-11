interface Props {
  value: string | null
  categories: string[]
  onChange: (value: string) => void
  disabled?: boolean
}

export default function CategorySelect({ value, categories, onChange, disabled }: Props) {
  return (
    <select
      value={value ?? ''}
      onChange={e => onChange(e.target.value)}
      disabled={disabled}
      className="w-full text-sm border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
    >
      <option value="">-- category --</option>
      {categories.map(c => (
        <option key={c} value={c}>{c}</option>
      ))}
    </select>
  )
}
