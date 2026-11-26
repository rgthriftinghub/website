import { ButtonLink } from "@/components/ui/button";

export const metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="max-w-md text-center">
        <p className="eyebrow">404</p>
        <h1 className="mt-3 text-4xl">This piece has moved on</h1>
        <p className="mt-3 text-sm text-ink-muted">
          Stock is one of a kind, so pages come and go. Try the shop for what is currently on the
          rail.
        </p>
        <div className="mt-8 flex justify-center gap-2.5">
          <ButtonLink href="/shop">Browse the shop</ButtonLink>
          <ButtonLink href="/" variant="secondary">
            Home
          </ButtonLink>
        </div>
      </div>
    </div>
  );
}
