"use client"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import { TIMEZONES } from "@/lib/timezones"

function TimezoneSelect({
  value,
  onValueChange,
  placeholder = "Select a timezone",
}: {
  value: string
  onValueChange: (value: string) => void
  placeholder?: string
}) {
  return (
    <Select
      value={value}
      onValueChange={(next) => {
        if (next !== null) {
          onValueChange(next)
        }
      }}
    >
      <SelectTrigger className="w-full justify-between">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent align="start">
        {TIMEZONES.map((timezone) => (
          <SelectItem key={timezone} value={timezone}>
            {timezone.replaceAll("_", " ")}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export { TimezoneSelect }
