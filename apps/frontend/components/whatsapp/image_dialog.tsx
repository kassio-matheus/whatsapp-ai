"use client"

import * as React from "react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import Image from "next/image"

function ImageDialog({
  open,
  onOpenChange,
  preview_url,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  preview_url: string
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[95dvh] w-[95vw] max-w-none flex-col overflow-hidden p-6 sm:max-w-[95vw]">
        <DialogHeader>
          <DialogTitle>Image preview</DialogTitle>
        </DialogHeader>

        <div className="relative min-h-0 w-full flex-1 overflow-hidden rounded-md">
          <Image
            src={preview_url}
            fill
            alt="Preview da imagem"
            className="object-contain"
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

export { ImageDialog }
