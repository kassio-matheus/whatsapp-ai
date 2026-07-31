export default function WhatsAppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4 p-4 md:p-6">{children}</div>
  )
}
