import { AdminProductEditor } from "@/components/admin/admin-product-editor";

export default async function AdminEditProductPage({ params }: { params: Promise<{ productId: string }> }) {
  const { productId } = await params;
  return <AdminProductEditor productId={productId} />;
}
