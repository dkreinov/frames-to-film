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
    lazy: async () => {
      const mod = await import('./PrepareScreen')
      return { Component: mod.default }
    },
  },
  {
    path: '/projects/:projectId/storyboard',
    lazy: async () => {
      const mod = await import('./StoryboardScreen')
      return { Component: mod.default }
    },
  },
  {
    path: '/projects/:projectId/generate',
    element: <div className="p-8">Generate — coming in next sub-plan</div>,
  },
])
