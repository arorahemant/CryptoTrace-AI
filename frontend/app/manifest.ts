import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'CryptoTrace AI — Investigator Workspace',
    short_name: 'CryptoTrace',
    description: 'Evidence-first blockchain fraud investigation workspace.',
    start_url: '/',
    display: 'standalone',
    background_color: '#fafaf5',
    theme_color: '#124343',
    icons: [
      {
        src: '/favicon.ico',
        sizes: 'any',
        type: 'image/x-icon',
      },
    ],
  };
}
