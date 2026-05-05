import { useRef, useState } from 'react'
import { Play, Pause, Download, Volume2, VolumeX } from 'lucide-react'

interface VideoPlayerProps {
  videoUrl: string
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function VideoPlayer({ videoUrl }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  const togglePlay = () => {
    const v = videoRef.current
    if (!v) return
    if (v.paused) { v.play(); setPlaying(true) }
    else { v.pause(); setPlaying(false) }
  }

  const toggleMute = () => {
    const v = videoRef.current
    if (!v) return
    v.muted = !v.muted
    setMuted(v.muted)
  }

  const handleTimeUpdate = () => {
    const v = videoRef.current
    if (!v || !v.duration) return
    setCurrentTime(v.currentTime)
    setProgress((v.currentTime / v.duration) * 100)
  }

  const handleLoadedMetadata = () => {
    const v = videoRef.current
    if (v) setDuration(v.duration)
  }

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const v = videoRef.current
    if (!v || !v.duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    v.currentTime = ((e.clientX - rect.left) / rect.width) * v.duration
  }

  return (
    <div className="w-full rounded-2xl overflow-hidden bg-black border border-white/8 shadow-xl animate-fade-in">
      <video
        ref={videoRef}
        src={videoUrl}
        className="w-full aspect-video"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={() => setPlaying(false)}
        preload="metadata"
      />

      <div className="bg-navy-800/95 px-4 py-3 space-y-2.5">
        {/* Seekbar */}
        <div
          className="w-full bg-white/10 rounded-full h-1 cursor-pointer group relative"
          onClick={handleSeek}
        >
          <div
            className="h-full rounded-full bg-indigo-500 group-hover:bg-indigo-400 transition-colors relative"
            style={{ width: `${progress}%` }}
          >
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity shadow" />
          </div>
        </div>

        {/* Controls row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <button
              onClick={togglePlay}
              className="p-2 rounded-lg hover:bg-white/8 text-white transition-colors"
            >
              {playing ? <Pause size={17} /> : <Play size={17} />}
            </button>
            <button
              onClick={toggleMute}
              className="p-2 rounded-lg hover:bg-white/8 text-slate-400 hover:text-white transition-colors"
            >
              {muted ? <VolumeX size={15} /> : <Volume2 size={15} />}
            </button>
            {duration > 0 && (
              <span className="text-xs text-slate-500 font-mono ml-1 tabular-nums">
                {formatTime(currentTime)} / {formatTime(duration)}
              </span>
            )}
          </div>

          <a
            href={videoUrl}
            download="explainer.mp4"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/80 hover:bg-indigo-600 text-white rounded-lg text-xs font-medium transition-colors"
          >
            <Download size={12} />
            Download
          </a>
        </div>
      </div>
    </div>
  )
}
