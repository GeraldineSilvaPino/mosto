// Keep the original values and elapsed time. Break the line across missing
// readings and long gaps instead of compressing them into adjacent categories.
export function telemetryPoints(timestamps = [], values = [], maxGapMs = 900000) {
  const points = []
  let previous
  timestamps.forEach((stamp, index) => {
    const x = new Date(stamp).getTime()
    if (!Number.isFinite(x)) return
    if (previous != null && x - previous > maxGapMs) points.push({ x: previous + 1, y: null })
    const value = values[index]
    points.push({ x, y: typeof value === 'number' && Number.isFinite(value) ? value : null })
    previous = x
  })
  return points
}
