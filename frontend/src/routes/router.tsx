import { createBrowserRouter, Navigate } from 'react-router-dom'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/projects/new/upload" replace />,
  },
  {
    path: '/projects/new/upload',
    lazy: async () => {
      const mod = await import('./UploadScreen')
      return { Component: mod.default }
    },
  },
  {
    path: '/projects/:projectId/upload',
    lazy: async () => {
      const mod = await import('./UploadScreen')
      return { Component: mod.default }
    },
  },
  {
    path: '/projects/:projectId/prepare',
    element: <div className="p-8">Prepare screen — coming in next sub-plan</div>,
  },
])
