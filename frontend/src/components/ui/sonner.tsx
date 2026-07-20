import { Toaster as SonnerToaster } from "sonner"

function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast: "glass-overlay rounded-md shadow-md",
          title: "text-sm text-zinc-900 dark:text-zinc-50",
          description: "text-xs text-zinc-500 dark:text-zinc-400",
        },
      }}
    />
  )
}

export { Toaster }
