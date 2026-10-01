import "./globals.css";

export const metadata = {
  title: "Urban Lab",
  description: "Urban data science and econometrics workspace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
