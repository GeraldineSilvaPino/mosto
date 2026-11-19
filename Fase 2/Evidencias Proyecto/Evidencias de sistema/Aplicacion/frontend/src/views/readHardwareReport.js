// Parse one complete report from the ESP32 central firmware.
export function readHardwareReport(report) {
  const cards = []
  const sections = report.split(/\[0[1-5]\]/)
  if (sections.length !== 6) return cards
  const [, wine, air, ph, float] = sections
  function number(section, label) {
    return section.match(new RegExp('^\\s*' + label + '\\s*:\\s*([+-]?\\d+(?:\\.\\d+)?)\\b', 'm'))?.[1]
  }
  const temperature = number(wine, 'Temperatura')
  if (temperature && /Comunicacion\s*:\s*CORRECTA/i.test(wine))
    cards.push({ sensor: 'DS18B20', label: 'Temperatura del vino', value: temperature + ' °C' })
  const ambient = number(air, 'Temperatura')
  const humidity = number(air, 'Humedad')
  if (ambient && humidity && /Comunicacion\s*:\s*CORRECTA/i.test(air))
    cards.push({ sensor: 'DHT22', label: 'Temperatura y humedad ambiente', value: ambient + ' °C · ' + humidity + ' %' })
  const voltage = number(ph, 'PO - voltaje estimado')
  if (voltage && /Entrada ADC\s*:\s*RANGO MONITOREADO/.test(ph) && /Salida PO\s*:\s*SENAL DETECTADA/.test(ph))
    cards.push({ sensor: 'PH-4502C', label: 'pH estimado · sin calibrar', value: (7 - (Number(voltage) - 2.5) / 0.18).toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) })
  const tilt = number(float, 'Inclinacion')
  if (tilt && /CONECTADO\s*\/\s*ENVIANDO DATOS/.test(float))
    cards.push({ sensor: 'MPU6050', label: 'Inclinación del flotador', value: tilt + '°' })
  return cards
}
