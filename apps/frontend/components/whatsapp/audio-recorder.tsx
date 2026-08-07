"use client"

import * as React from "react"
import {
  AudioLines,
  LoaderCircle,
  Mic,
  Pause,
  Play,
  Send,
  Trash2,
  Volume2,
} from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { cn } from "@workspace/ui/lib/utils"

const MAX_RECORDING_SECONDS = 300
const BAR_COUNT = 72
const BAR_GAP = 2

// Formatos "de matéria-prima" que o MediaRecorder do navegador consegue
// gravar nativamente. Nenhum deles é enviado direto ao WhatsApp — servem
// só de entrada para a transcodificação real feita pelo ffmpeg.wasm em
// transcodeToOggOpus(). Por isso podemos aceitar webm aqui sem problema.
const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",
]

function pickRecorderMimeType() {
  if (typeof MediaRecorder === "undefined") {
    return null
  }
  return (
    MIME_CANDIDATES.find((candidate) =>
      MediaRecorder.isTypeSupported(candidate)
    ) ?? null
  )
}

function nativeExtensionForMime(mimeType: string) {
  if (mimeType.includes("webm")) {
    return "webm"
  }
  if (mimeType.includes("ogg")) {
    return "ogg"
  }
  if (mimeType.includes("mp4")) {
    return "mp4"
  }
  return "bin"
}

// ---------------------------------------------------------------------
// ffmpeg.wasm: carregado sob demanda (import dinâmico) e mantido como
// singleton no módulo para ser reaproveitado entre gravações na mesma
// sessão. Usa o core single-thread (@ffmpeg/core), que NÃO exige os
// headers Cross-Origin-Opener-Policy / Cross-Origin-Embedder-Policy no
// servidor — só o core multi-thread (@ffmpeg/core-mt) exige isso.
// ---------------------------------------------------------------------
type FFmpegInstance = import("@ffmpeg/ffmpeg").FFmpeg

let ffmpegSingleton: FFmpegInstance | null = null
let ffmpegLoadPromise: Promise<FFmpegInstance> | null = null

async function getFFmpeg(): Promise<FFmpegInstance> {
  if (ffmpegSingleton) {
    return ffmpegSingleton
  }
  if (!ffmpegLoadPromise) {
    ffmpegLoadPromise = (async () => {
      const [{ FFmpeg }, { toBlobURL }] = await Promise.all([
        import("@ffmpeg/ffmpeg"),
        import("@ffmpeg/util"),
      ])
      const ffmpeg = new FFmpeg()
      const baseURL = "https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm"
      await ffmpeg.load({
        coreURL: await toBlobURL(
          `${baseURL}/ffmpeg-core.js`,
          "text/javascript"
        ),
        wasmURL: await toBlobURL(
          `${baseURL}/ffmpeg-core.wasm`,
          "application/wasm"
        ),
        classWorkerURL: `${window.location.origin}/ffmpeg/worker.js`,
      })
      ffmpegSingleton = ffmpeg
      return ffmpeg
    })().catch((err) => {
      // Permite tentar carregar de novo numa próxima gravação se falhar.
      console.error("[AudioRecorder] transcodificação falhou:", err)

      ffmpegLoadPromise = null
      throw err
    })
  }
  return ffmpegLoadPromise
}

/**
 * Transcodifica qualquer áudio de entrada (webm/opus, mp4/aac, ogg/opus
 * etc.) para um Ogg/Opus mono de verdade — nos bytes, não só no rótulo —
 * exatamente como a WhatsApp Cloud API exige. Isso elimina o problema de
 * navegadores que "muxam" Opus dentro de um contêiner MP4 sem o áudio
 * estar de fato em AAC (o que a Meta rejeita como application/octet-stream).
 */
async function transcodeToOggOpus(
  rawBlob: Blob,
  rawExtension: string
): Promise<Blob> {
  const { fetchFile } = await import("@ffmpeg/util")
  const ffmpeg = await getFFmpeg()

  const inputName = `input-${Date.now()}.${rawExtension}`
  const outputName = `output-${Date.now()}.ogg`

  await ffmpeg.writeFile(inputName, await fetchFile(rawBlob))
  try {
    await ffmpeg.exec([
      "-i",
      inputName,
      "-ac",
      "1", // mono — exigido pela WhatsApp Cloud API para Ogg
      "-c:a",
      "libopus",
      "-b:a",
      "32k",
      "-vn",
      outputName,
    ])
    const data = await ffmpeg.readFile(outputName)
    const bytes =
      data instanceof Uint8Array ? new Uint8Array(data) : new TextEncoder().encode(String(data))
    return new Blob([bytes], { type: "audio/ogg; codecs=opus" })
  } finally {
    try {
      await ffmpeg.deleteFile(inputName)
    } catch (err) {
      console.log(err)
      // ignore
    }
    try {
      await ffmpeg.deleteFile(outputName)
    } catch (err) {
      console.log(err)
      // ignore
    }
  }
}

function formatClock(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  if (hours > 0) {
    return `${hours}:${String(minutes % 60).padStart(2, "0")}:${String(
      seconds % 60
    ).padStart(2, "0")}`
  }
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`
}

function themeColor(variable: string) {
  if (typeof window === "undefined") {
    return "currentColor"
  }
  return (
    getComputedStyle(document.documentElement)
      .getPropertyValue(variable)
      .trim() || "currentColor"
  )
}

function AudioRecorder({
  disabled = false,
  onUpload,
  onSend,
  onActiveChange,
  onError,
}: {
  disabled?: boolean
  onUpload?: (file: File) => Promise<string>
  onSend: (data: {
    message_type: string
    media_url: string
    content?: string
    metadata?: Record<string, unknown>
  }) => Promise<void>
  onActiveChange?: (active: boolean) => void
  onError?: (message: string | null) => void
}) {
  const [status, setStatus] = React.useState<
    "idle" | "recording" | "converting" | "preview" | "uploading"
  >("idle")
  const [recordingSeconds, setRecordingSeconds] = React.useState(0)
  const [previewSeconds, setPreviewSeconds] = React.useState(0)

  const mediaRecorderRef = React.useRef<MediaRecorder | null>(null)
  const chunksRef = React.useRef<Blob[]>([])
  // Blob no formato nativo do navegador — usado só para tocar o preview
  // local (sempre tocável no mesmo navegador que gravou).
  const nativeBlobRef = React.useRef<Blob | null>(null)
  const nativeExtensionRef = React.useRef<string>("webm")
  // Blob já transcodificado para Ogg/Opus mono real — é o que de fato
  // vai no upload para a WhatsApp Cloud API.
  const uploadBlobRef = React.useRef<Blob | null>(null)
  const uploadPromiseRef = React.useRef<Promise<Blob> | null>(null)
  const streamRef = React.useRef<MediaStream | null>(null)
  const audioContextRef = React.useRef<AudioContext | null>(null)
  const analyserRef = React.useRef<AnalyserNode | null>(null)
  const micSourceRef = React.useRef<MediaStreamAudioSourceNode | null>(null)
  const canvasRef = React.useRef<HTMLCanvasElement>(null)
  const audioRef = React.useRef<HTMLAudioElement>(null)
  const objectUrlRef = React.useRef<string | null>(null)
  const animationFrameRef = React.useRef<number | null>(null)
  const timerIntervalRef = React.useRef<ReturnType<typeof setInterval> | null>(
    null
  )
  const waveformRef = React.useRef<number[] | null>(null)
  const durationRef = React.useRef(0)
  const drawingRef = React.useRef<"idle" | "live" | "preview">("idle")
  const playbackTimeRef = React.useRef(0)
  const isPlayingRef = React.useRef(false)
  const finalizedRef = React.useRef(false)
  const [localError, setLocalError] = React.useState<string | null>(null)

  function reportError(message: string | null) {
    setLocalError(message)
    onError?.(message)
  }

  function teardownMic() {
    streamRef.current?.getTracks().forEach((track) => {
      try {
        track.stop()
      } catch (err) {
        // ignore
        console.log(err)
      }
    })
    streamRef.current = null
    micSourceRef.current?.disconnect()
    micSourceRef.current = null
  }

  async function ensureAudioContext() {
    if (audioContextRef.current) {
      return audioContextRef.current
    }
    const context = new AudioContext()
    audioContextRef.current = context
    const analyser = context.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0.84
    analyserRef.current = analyser
    return context
  }

  async function startRecording() {
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      reportError("Audio recording is not supported in this browser.")
      return
    }
    const mimeType = pickRecorderMimeType()
    if (!mimeType) {
      reportError("Audio recording is not supported in this browser.")
      return
    }
    reportError(null)
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      })
    } catch (err) {
      console.log(err)
      reportError("Microphone access was denied or no microphone is available.")
      return
    }
    chunksRef.current = []
    nativeBlobRef.current = null
    uploadBlobRef.current = null
    uploadPromiseRef.current = null
    finalizedRef.current = false
    streamRef.current = stream
    try {
      const context = await ensureAudioContext()
      if (context.state === "suspended") {
        await context.resume()
      }
      if (analyserRef.current) {
        const source = context.createMediaStreamSource(stream)
        source.connect(analyserRef.current)
        micSourceRef.current = source
      }
    } catch (err) {
      console.log(err)
      // Live visualization is optional; recording still works without it.
    }

    const recorder = new MediaRecorder(stream, {
      mimeType,
      audioBitsPerSecond: 128000,
    })
    mediaRecorderRef.current = recorder
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        chunksRef.current.push(event.data)
      }
    }
    recorder.onerror = () => {
      reportError("The audio recorder failed while recording.")
      void finalizeRecording(mimeType)
    }
    recorder.onstop = () => {
      void finalizeRecording(mimeType)
    }
    recorder.start(250)

    const startedAt = Date.now()
    drawingRef.current = "live"
    durationRef.current = 0
    playbackTimeRef.current = 0
    isPlayingRef.current = false
    setRecordingSeconds(0)
    setPreviewSeconds(0)
    setStatus("recording")
    onActiveChange?.(true)
    timerIntervalRef.current = setInterval(() => {
      const elapsed = (Date.now() - startedAt) / 1000
      setRecordingSeconds(elapsed)
      if (elapsed >= MAX_RECORDING_SECONDS) {
        stopRecording()
      }
    }, 250)
    startAnimationLoop()
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== "inactive") {
      try {
        recorder.stop()
      } catch (err) {
        console.log(err)
        // The stop event may already have fired.
      }
    }
  }

  // Dispara (ou reaproveita) a transcodificação para Ogg/Opus real.
  // Chamada tanto logo após a gravação parar (para converter em segundo
  // plano enquanto a pessoa revê a gravação) quanto, de forma garantida,
  // dentro de handleSend antes do upload.
  function ensureUploadBlob(): Promise<Blob> {
    if (uploadBlobRef.current) {
      return Promise.resolve(uploadBlobRef.current)
    }
    if (uploadPromiseRef.current) {
      return uploadPromiseRef.current
    }
    const raw = nativeBlobRef.current
    if (!raw) {
      return Promise.reject(new Error("No recording available"))
    }
    const promise = transcodeToOggOpus(raw, nativeExtensionRef.current)
      .then((ogg) => {
        uploadBlobRef.current = ogg
        return ogg
      })
      .catch((err) => {
        console.log(err)
        uploadPromiseRef.current = null
        throw err
      })
    uploadPromiseRef.current = promise
    return promise
  }

  async function finalizeRecording(mimeType: string) {
    if (finalizedRef.current) {
      return
    }
    finalizedRef.current = true
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
    teardownMic()
    mediaRecorderRef.current = null
    drawingRef.current = "preview"
    playbackTimeRef.current = 0
    isPlayingRef.current = false

    nativeExtensionRef.current = nativeExtensionForMime(mimeType)
    const blob = new Blob(chunksRef.current, { type: mimeType })
    nativeBlobRef.current = blob

    let decodedDuration = 0
    try {
      const context = audioContextRef.current
      if (context) {
        const buffer = await context.decodeAudioData(await blob.arrayBuffer())
        if (buffer.duration > 0) {
          decodedDuration = buffer.duration
          const channel = buffer.getChannelData(0)
          const samplesPerBar = Math.max(
            1,
            Math.floor(channel.length / (BAR_COUNT * 2))
          )
          const bars: number[] = []
          for (let i = 0; i < BAR_COUNT; i += 1) {
            const start = i * samplesPerBar
            const end = Math.min(channel.length, start + samplesPerBar)
            let sum = 0
            for (let j = start; j < end; j += 1) {
              const value = channel[j] ?? 0
              sum += value * value
            }
            const rms = Math.sqrt(sum / Math.max(1, end - start))
            bars.push(Math.min(1, rms * 3.2 + 0.04))
          }
          waveformRef.current = bars
        }
      }
    } catch (err) {
      console.log(err)
      decodedDuration = 0
    }
    if (!waveformRef.current || decodedDuration === 0) {
      waveformRef.current = Array.from({ length: BAR_COUNT }, (_, index) =>
        Math.min(1, 0.12 + Math.abs(Math.sin(index * 1.27)) * 0.6)
      )
    }

    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current)
    }
    // O preview toca o blob nativo (o mesmo que o navegador gravou),
    // garantindo que sempre haja suporte de reprodução.
    objectUrlRef.current = URL.createObjectURL(blob)
    setPreviewSeconds(decodedDuration)

    // Começa a converter para Ogg/Opus real em segundo plano assim que a
    // gravação termina, para que o envio depois seja quase instantâneo.
    setStatus("converting")
    try {
      await ensureUploadBlob()
      reportError(null)
    } catch (err) {
      console.error("[AudioRecorder] transcodificação falhou:", err)

      reportError(
        "Could not convert the recording to a WhatsApp-compatible format. You can still try sending it."
      )
    } finally {
      setStatus("preview")
    }
  }

  function togglePlayback() {
    const audio = audioRef.current
    if (!audio) {
      return
    }
    if (isPlayingRef.current) {
      audio.pause()
    } else {
      void audio.play()
    }
  }

  function handleTimeUpdate() {
    const audio = audioRef.current
    if (!audio) {
      return
    }
    playbackTimeRef.current = audio.currentTime
    durationRef.current = audio.duration || durationRef.current
    setPreviewSeconds(durationRef.current)
  }

  async function handleSend() {
    if (status !== "preview") {
      return
    }
    setStatus("uploading")
    reportError(null)

    let blob: Blob
    try {
      // Garante que existe (ou espera terminar) a versão transcodificada
      // em Ogg/Opus real antes de subir qualquer coisa.
      blob = await ensureUploadBlob()
    } catch (err) {
      console.error("[AudioRecorder] transcodificação falhou no envio:", err)

      reportError(
        "Could not convert the recording to a WhatsApp-compatible format."
      )
      setStatus("preview")
      return
    }
    if (!onUpload) {
      reportError("Media upload is unavailable for this conversation.")
      setStatus("preview")
      return
    }
    const file = new File([blob], `voice-message-${Date.now()}.ogg`, {
      type: "audio/ogg; codecs=opus",
    })
    try {
      const url = await onUpload(file)
      await onSend({
        message_type: "audio",
        media_url: url,
        metadata: {
          filename: file.name,
          mime_type: file.type,
          origin: "composer-recorder",
        },
      })
      resetToIdle()
    } catch (err) {
      console.log(err)
      reportError(
        err instanceof Error ? err.message : "Could not upload the recording."
      )
      setStatus("preview")
    }
  }

  function resetToIdle() {
    cleanup()
    onActiveChange?.(false)
    setStatus("idle")
  }

  function cleanupTimer() {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
  }

  function cleanup() {
    stopAnimationLoop()
    cleanupTimer()
    teardownMic()
    if (mediaRecorderRef.current) {
      const recorder = mediaRecorderRef.current
      mediaRecorderRef.current = null
      if (recorder.state !== "inactive") {
        finalizedRef.current = true
        try {
          recorder.stop()
        } catch (err) {
          console.log(err)
          // ignore
        }
      }
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current)
      objectUrlRef.current = null
    }
    waveformRef.current = null
    drawingRef.current = "idle"
    nativeBlobRef.current = null
    uploadBlobRef.current = null
    uploadPromiseRef.current = null
    finalizedRef.current = false
  }

  function startAnimationLoop() {
    if (animationFrameRef.current !== null) {
      return
    }
    const loop = () => {
      drawWaveform()
      animationFrameRef.current = requestAnimationFrame(loop)
    }
    animationFrameRef.current = requestAnimationFrame(loop)
  }

  function stopAnimationLoop() {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }
  }

  function drawWaveform() {
    const canvas = canvasRef.current
    if (!canvas) {
      return
    }
    const dpr = window.devicePixelRatio || 1
    const width = canvas.clientWidth
    const height = canvas.clientHeight
    if (width === 0 || height === 0) {
      return
    }
    const targetWidth = Math.round(width * dpr)
    const targetHeight = Math.round(height * dpr)
    if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
      canvas.width = targetWidth
      canvas.height = targetHeight
    }
    const context = canvas.getContext("2d")
    if (!context) {
      return
    }
    context.save()
    context.setTransform(dpr, 0, 0, dpr, 0, 0)
    context.clearRect(0, 0, width, height)

    const primary = themeColor("--primary")
    const dim = themeColor("--ring") || primary
    const muted = themeColor("--muted-foreground")
    const barWidth = (width - BAR_GAP * (BAR_COUNT - 1)) / BAR_COUNT
    const center = height / 2
    const maxBarHeight = height - 4
    const mode = drawingRef.current

    for (let i = 0; i < BAR_COUNT; i += 1) {
      let amplitude = 0.1
      if (mode === "live" && analyserRef.current) {
        const frequencies = new Uint8Array(
          analyserRef.current.frequencyBinCount
        )
        analyserRef.current.getByteFrequencyData(frequencies)
        const group = Math.max(1, Math.floor(frequencies.length / BAR_COUNT))
        const start = i * group
        const end = Math.min(frequencies.length, start + group)
        let sum = 0
        for (let j = start; j < end; j += 1) {
          sum += frequencies[j] ?? 0
        }
        amplitude = sum / Math.max(1, end - start) / 255
      } else if (mode === "preview") {
        const bars = waveformRef.current
        if (bars) {
          amplitude = bars[i] ?? 0.1
        }
      } else {
        amplitude = 0.09 + Math.abs(Math.sin(Date.now() / 900 + i * 0.6)) * 0.1
      }

      const barHeight = Math.min(
        maxBarHeight,
        Math.max(2, amplitude * maxBarHeight)
      )

      context.fillStyle = muted
      context.globalAlpha = 0.15
      context.fillRect(i * (barWidth + BAR_GAP), 2, barWidth, height - 4)
      context.globalAlpha = 1

      if (mode === "preview") {
        const progress =
          durationRef.current > 0
            ? playbackTimeRef.current / durationRef.current
            : 0
        const played = (i + 1) / BAR_COUNT <= progress
        context.fillStyle = played ? primary : dim
        context.globalAlpha = played ? 1 : 0.55
      } else {
        context.fillStyle = primary
        context.globalAlpha = 0.35 + Math.min(1, amplitude) * 0.65
      }
      context.fillRect(
        i * (barWidth + BAR_GAP),
        center - barHeight / 2,
        barWidth,
        barHeight
      )
      context.globalAlpha = 1
    }

    if (mode === "preview" && durationRef.current > 0) {
      const progress = playbackTimeRef.current / durationRef.current
      context.fillStyle = primary
      context.globalAlpha = 0.9
      context.fillRect(Math.max(0, progress * width), 0, 1.5, height)
      context.globalAlpha = 1
    }

    context.restore()
  }

  // Pré-carrega o ffmpeg.wasm assim que o componente monta, em segundo
  // plano, para esconder a latência do download (~30MB) atrás do tempo
  // que a pessoa leva gravando o áudio.
  React.useEffect(() => {
    if (disabled) {
      return
    }
    void getFFmpeg().catch(() => {
      // Silencioso aqui — se falhar, tentamos de novo quando a pessoa
      // realmente gravar algo, e o erro será mostrado nesse momento.
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  React.useEffect(() => {
    return () => {
      cleanup()
      if (audioContextRef.current) {
        void audioContextRef.current.close()
        audioContextRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  React.useEffect(() => {
    if (status === "recording") {
      startAnimationLoop()
    } else if (status === "idle") {
      stopAnimationLoop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status])

  const active = status !== "idle"

  if (!active) {
    return (
      <Button
        type="button"
        variant="outline"
        size="icon"
        onClick={() => void startRecording()}
        disabled={disabled}
        title={
          disabled
            ? "Recording is unavailable for this conversation."
            : "Record an audio message"
        }
        aria-label="Record an audio message"
        className="shrink-0 hover:border-primary/40 hover:text-primary"
      >
        <Mic className="size-4" />
      </Button>
    )
  }

  const isRecording = status === "recording"
  const isConverting = status === "converting"
  const isPreview = status === "preview"

  return (
    <div
      className={cn(
        "w-full min-w-0 shrink-0 animate-pop rounded-none border p-2",
        isRecording
          ? "border-destructive/30 bg-destructive/[0.03]"
          : "border-primary/25 bg-primary/[0.04]"
      )}
      role="status"
      aria-live="assertive"
    >
      <audio
        ref={audioRef}
        src={objectUrlRef.current ?? undefined}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleTimeUpdate}
        onPlay={() => {
          isPlayingRef.current = true
        }}
        onPause={() => {
          isPlayingRef.current = false
        }}
        onEnded={() => {
          isPlayingRef.current = false
          playbackTimeRef.current = 0
        }}
        className="hidden"
      />

      {status === "uploading" ? (
        <div className="flex h-9 w-full items-center justify-center gap-2">
          <LoaderCircle className="size-4 animate-spin text-primary" />
          <span className="text-[11px] text-muted-foreground">
            Saving the recording to R2…
          </span>
          <div className="h-1 w-28 overflow-hidden rounded-full bg-muted">
            <div className="h-full w-1/2 animate-shimmer bg-[linear-gradient(90deg,transparent,color-mix(in_oklch,var(--primary)_70%,transparent),transparent)]" />
          </div>
        </div>
      ) : isConverting ? (
        <div className="flex h-9 w-full items-center justify-center gap-2">
          <LoaderCircle className="size-4 animate-spin text-primary" />
          <span className="text-[11px] text-muted-foreground">
            Converting to Ogg/Opus for WhatsApp…
          </span>
          <div className="h-1 w-28 overflow-hidden rounded-full bg-muted">
            <div className="h-full w-1/2 animate-shimmer bg-[linear-gradient(90deg,transparent,color-mix(in_oklch,var(--primary)_70%,transparent),transparent)]" />
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => (isRecording ? stopRecording() : togglePlayback())}
            className={cn(
              "flex size-9 shrink-0 items-center justify-center rounded-full transition-all",
              isRecording
                ? "text-destructive-foreground animate-pulse-soft bg-destructive hover:bg-destructive/90"
                : "bg-primary text-primary-foreground hover:bg-primary/90"
            )}
            aria-label={
              isRecording
                ? "Stop recording"
                : isPlayingRef.current
                  ? "Pause audio"
                  : "Play audio"
            }
            title={
              isRecording
                ? "Stop recording"
                : isPlayingRef.current
                  ? "Pause audio"
                  : "Preview the recording"
            }
          >
            {isRecording ? (
              <span className="block size-3 animate-pulse bg-background" />
            ) : isPlayingRef.current ? (
              <Pause className="size-4" />
            ) : (
              <Play className="size-4 ps-0.5" />
            )}
          </button>

          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <canvas ref={canvasRef} className="h-9 w-full" aria-hidden="true" />
            <div className="flex items-center gap-2">
              {isRecording ? (
                <>
                  <span className="flex items-center gap-1.5 text-[10px] font-medium tracking-wider text-destructive uppercase">
                    <span className="relative flex size-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-destructive opacity-75" />
                      <span className="relative inline-flex size-1.5 rounded-full bg-destructive" />
                    </span>
                    Recording
                  </span>
                  <span className="ms-auto font-mono text-[11px] text-foreground/85 tabular-nums">
                    {formatClock(recordingSeconds)} /{" "}
                    {formatClock(MAX_RECORDING_SECONDS)}
                  </span>
                </>
              ) : (
                <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                  <Volume2 className="size-3" />
                  <span className="font-mono tabular-nums">
                    {formatClock(playbackTimeRef.current)}
                  </span>
                  <span>/</span>
                  <span className="font-mono tabular-nums">
                    {formatClock(previewSeconds)}
                  </span>
                </div>
              )}
            </div>
          </div>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="shrink-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={resetToIdle}
            title="Discard recording"
            aria-label="Discard recording"
          >
            <Trash2 className="size-4" />
          </Button>

          {isPreview ? (
            <Button
              type="button"
              size="icon"
              className="shrink-0"
              onClick={() => void handleSend()}
              title="Convert (if needed) and send as an audio message"
              aria-label="Send audio message"
            >
              <Send className="size-4" />
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="shrink-0"
              onClick={togglePlayback}
              title="Preview the recording"
              aria-label="Preview the recording"
            >
              <AudioLines className="size-4" />
            </Button>
          )}
        </div>
      )}
      {localError ? (
        <p className="pt-1 text-[10px] text-destructive">{localError}</p>
      ) : null}
    </div>
  )
}

export { AudioRecorder }
