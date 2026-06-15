import { ImageResponse } from 'next/og'

// PeerForge favicon — copper "PF" monogram on scholarly indigo
export const size = { width: 64, height: 64 }
export const contentType = 'image/png'

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#1E1B4B',
          borderRadius: 14,
          color: '#C47A3A',
          fontSize: 30,
          fontWeight: 700,
          fontFamily: 'Georgia, "Times New Roman", serif',
          letterSpacing: -1,
        }}
      >
        PF
      </div>
    ),
    { ...size }
  )
}
