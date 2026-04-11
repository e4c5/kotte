import { RefObject } from 'react'

interface UseGraphExportProps {
  svgRef: RefObject<SVGSVGElement>
  width: number
  height: number
}

export function useGraphExport({ svgRef, width, height }: UseGraphExportProps) {
  const exportToPNG = async (): Promise<void> => {
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
    
    // Create an image element
    const img = new Image()
    
    return new Promise((resolve, reject) => {
      img.onload = () => {
        try {
          // Create a canvas
          const canvas = document.createElement('canvas')
          canvas.width = width
          canvas.height = height
          const ctx = canvas.getContext('2d')
          
          if (!ctx) {
            reject(new Error('Could not get canvas context'))
            return
          }
          
          // Fill white background
          ctx.fillStyle = 'white'
          ctx.fillRect(0, 0, canvas.width, canvas.height)
          
          // Draw the image onto the canvas
          ctx.drawImage(img, 0, 0)
          
          // Convert canvas to PNG blob
          canvas.toBlob((blob) => {
            if (!blob) {
              reject(new Error('Failed to create PNG blob'))
              return
            }
            
            // Create download link
            const downloadUrl = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = downloadUrl
            link.download = `graph-export-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.png`
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            
            // Cleanup
            URL.revokeObjectURL(url)
            URL.revokeObjectURL(downloadUrl)
            
            resolve()
          }, 'image/png')
        } catch (error) {
          URL.revokeObjectURL(url)
          reject(error)
        }
      }
      
      img.onerror = () => {
        URL.revokeObjectURL(url)
        reject(new Error('Failed to load SVG image'))
      }
      
      img.src = url
    })
  }

  return { exportToPNG }
}
