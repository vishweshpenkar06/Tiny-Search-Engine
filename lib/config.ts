export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000',
  appName: process.env.NEXT_PUBLIC_APP_NAME || 'Tiny Search Engine',
  isDev: process.env.NODE_ENV === 'development',
}
