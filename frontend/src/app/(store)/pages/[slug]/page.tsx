import { StoreInfoPage } from "@/components/content/store-info-page";

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <StoreInfoPage slug={slug} />;
}
