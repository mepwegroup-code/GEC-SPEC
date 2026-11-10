import './style.css';
import type { Metadata } from 'next';
export const metadata:Metadata={title:'GEC Specifications | Lighting Engineering',description:'Lighting specifications and datasheet automation'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="vi"><body>{children}</body></html>}
