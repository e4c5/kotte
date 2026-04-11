import { RefObject, useCallback } from 'react'

interface UseGraphExportProps {
  svgRef: RefObject<SVGSVGElement>
  width: number
  height: number
}

const triggerDownload = (blob: Blob, svgObjectUrl: string) => {
  const pngObjectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = pngObjectUrl
  link.download = `graph-export-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.png`
  document.body.appendChild(link)
  link.click()
  link.remove()

  URL.revokeObjectURL(svgObjectUrl)
  // Defer revoking the PNG blob URL so the download can start before revoke runs.
  queueMicrotask(() => URL.revokeObjectURL(pngObjectUrl))
}

function finalizePngBlob(
  blob: Blob | null,
  svgObjectUrl: string,
  resolve: () => void,
  reject: (reason?: unknown) => void,
): void {
  if (!blob) {
    URL.revokeObjectURL(svgObjectUrl)
    reject(new Error('Failed to create PNG blob'))
    return
  }
  triggerDownload(blob, svgObjectUrl)
  resolve()
}

function drawSvgToPngBlob(
  img: HTMLImageElement,
  svgObjectUrl: string,
  width: number,
  height: number,
  resolve: () => void,
  reject: (reason?: unknown) => void,
): void {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')

  if (!ctx) {
    URL.revokeObjectURL(svgObjectUrl)
    reject(new Error('Could not get canvas context'))
    return
  }

  ctx.fillStyle = 'white'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(img, 0, 0)

  canvas.toBlob(
    (blob) => finalizePngBlob(blob, svgObjectUrl, resolve, reject),
    'image/png',
  )
}

function attachSvgExportHandlers(
  img: HTMLImageElement,
  svgObjectUrl: string,
  width: number,
  height: number,
  resolve: () => void,
  reject: (reason?: unknown) => void,
): void {
  img.onload = () => {
    try {
      drawSvgToPngBlob(img, svgObjectUrl, width, height, resolve, reject)
    } catch (error) {
      URL.revokeObjectURL(svgObjectUrl)
      reject(error)
    }
  }

  img.onerror = () => {
    URL.revokeObjectURL(svgObjectUrl)
    reject(new Error('Failed to load SVG image'))
  }
}

export function useGraphExport({ svgRef, width, height }: UseGraphExportProps) {
  const exportToPNG = useCallback(async (): Promise<void> => {
    if (!svgRef.current) {
      throw new Error('SVG element not found')
    }

    const svg = svgRef.current

    // Clone the SVG to avoid modifying the original
    const clonedSvg = svg.cloneNode(true) as SVGSVGElement

    // Get the transform from the zoom container
    const container = svg.querySelector('g')
    if (container) {
      const transform = container.getAttribute('transform')
      if (transform) {
        // Apply transform to all children
        const children = clonedSvg.querySelector('g')
        if (children) {
          children.setAttribute('transform', transform)
        }
      }
    }

    // Serialize SVG to string
    const serializer = new XMLSerializer()
    const svgString = serializer.serializeToString(clonedSvg)

    // Create a data URL
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)

    const img = new Image()

    return new Promise((resolve, reject) => {
      attachSvgExportHandlers(img, url, width, height, resolve, reject)
      img.src = url
    })
  }, [svgRef, width, height])

  return { exportToPNG }
}
