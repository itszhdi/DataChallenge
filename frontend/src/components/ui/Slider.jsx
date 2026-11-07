import * as RadixSlider from '@radix-ui/react-slider'

export default function Slider({ label, value, min, max, onChange }) {
  return (
    <RadixSlider.Root
      value={[value]}
      min={min}
      max={max}
      step={1}
      onValueChange={([next]) => onChange(next)}
      className="relative flex h-5 w-full touch-none items-center select-none"
    >
      <RadixSlider.Track className="relative h-1.5 grow rounded-full bg-surface-muted">
        <RadixSlider.Range className="absolute h-full rounded-full bg-brand" />
      </RadixSlider.Track>
      <RadixSlider.Thumb aria-label={label} className="block size-5 rounded-full border-2 border-brand bg-surface shadow" />
    </RadixSlider.Root>
  )
}
