import { ImageResponse } from 'next/og'

// PeerForge Apple touch icon — copper "PF" with rule on scholarly indigo
export const size = { width: 180, height: 180 }
export const contentType = 'image/png'

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#1E1B4B',
          color: '#C47A3A',
          fontFamily: 'Georgia, "Times New Roman", serif',
        }}
      >
        <div style={{ fontSize: 84, fontWeight: 700, lineHeight: 1, letterSpacing: -3 }}>PF</div>
        <div style={{ width: 72, height: 4, background: '#06B6D4', borderRadius: 2, marginTop: 10 }} />
      </div>
    ),
    { ...size }
  )
}
