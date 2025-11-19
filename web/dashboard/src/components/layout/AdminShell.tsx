import { ToastContainer } from "../ui/ToastContainer";

type AdminShellProps = {
  title: string;
  description?: string;
  children: React.ReactNode;
};

export function AdminShell({ title, description, children }: AdminShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-background-light text-text-primaryLight transition-colors dark:bg-background-dark dark:text-text-primaryDark">
      <ToastContainer />
      <header className="border-b border-border-light bg-background-cardLight px-8 py-6 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
        <h1 className="text-xl font-semibold tracking-tight text-text-primaryLight dark:text-text-primaryDark">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-sm text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
        ) : null}
      </header>
      <main className="flex flex-1 flex-col gap-6 p-8">{children}</main>
    </div>
  );
}
