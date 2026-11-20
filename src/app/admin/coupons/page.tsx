"use client";

import { useEffect, useState } from "react";
import { AdminGate } from "@/components/admin/admin-gate";
import { Button } from "@/components/ui/button";
import { createCoupon, deleteCoupon, listCoupons, type AdminCoupon } from "@/lib/api/admin";

export default function CouponsPage() {
  const [rows,setRows]=useState<AdminCoupon[]>([]); const [code,setCode]=useState("");
  const [discountType,setDiscountType]=useState<"PERCENTAGE"|"FIXED_AMOUNT">("PERCENTAGE");
  const [value,setValue]=useState(""); const [minimum,setMinimum]=useState("0"); const [max,setMax]=useState("");
  const [error,setError]=useState(""); const [busy,setBusy]=useState(false);
  async function refresh(){setRows(await listCoupons());}
  useEffect(()=>{void refresh().catch(()=>setError("Could not load coupons."));},[]);
  async function submit(event:React.FormEvent){event.preventDefault();setBusy(true);setError("");try{await createCoupon({code,discount_type:discountType,discount_value:value,minimum_order:minimum,max_redemptions:max?Number(max):null,starts_at:null,ends_at:null,is_active:true});setCode("");setValue("");await refresh();}catch(cause){setError(cause instanceof Error?cause.message:"Could not save coupon.");}finally{setBusy(false);}}
  async function remove(id:string){try{await deleteCoupon(id);await refresh();}catch{setError("Could not delete coupon.");}}
  return <AdminGate><main className="mx-auto max-w-6xl space-y-7 px-5 py-10"><header><p className="text-xs uppercase tracking-widest text-stone">Marketing</p><h1 className="mt-2 font-display text-3xl">Coupons & promo codes</h1></header>
    <form onSubmit={submit} className="grid gap-3 border border-line bg-surface p-5 sm:grid-cols-2 lg:grid-cols-5">
      <input required value={code} onChange={e=>setCode(e.target.value)} placeholder="Code e.g. WELCOME10" className="border border-line bg-paper px-3 py-2 text-sm" />
      <select value={discountType} onChange={e=>setDiscountType(e.target.value as typeof discountType)} className="border border-line bg-paper px-3 py-2 text-sm"><option value="PERCENTAGE">Percentage</option><option value="FIXED_AMOUNT">Fixed PKR</option></select>
      <input required type="number" min="0.01" step="0.01" value={value} onChange={e=>setValue(e.target.value)} placeholder="Discount" className="border border-line bg-paper px-3 py-2 text-sm" />
      <input type="number" min="0" step="0.01" value={minimum} onChange={e=>setMinimum(e.target.value)} placeholder="Minimum cart PKR" className="border border-line bg-paper px-3 py-2 text-sm" />
      <input type="number" min="1" value={max} onChange={e=>setMax(e.target.value)} placeholder="Max uses (optional)" className="border border-line bg-paper px-3 py-2 text-sm" />
      <div className="sm:col-span-2 lg:col-span-5"><Button disabled={busy}>{busy?"Saving…":"Create coupon"}</Button></div>
      {error?<p role="alert" className="text-sm text-danger sm:col-span-2 lg:col-span-5">{error}</p>:null}
    </form>
    <div className="overflow-x-auto border border-line bg-surface"><table className="w-full min-w-[44rem] text-sm"><thead><tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-stone"><th className="p-4">Code</th><th className="p-4">Discount</th><th className="p-4">Minimum order</th><th className="p-4">Redemptions</th><th className="p-4">Status</th><th className="p-4"></th></tr></thead><tbody>{rows.map(row=><tr key={row.id} className="border-b border-line/60"><td className="p-4 font-mono font-semibold">{row.code}</td><td className="p-4">{row.discount_type==="PERCENTAGE"?`${row.discount_value}%`:`PKR ${row.discount_value}`}</td><td className="p-4">PKR {row.minimum_order}</td><td className="p-4">{row.redemption_count}{row.max_redemptions?` / ${row.max_redemptions}`:""}</td><td className="p-4">{row.is_active?"Active":"Inactive"}</td><td className="p-4"><button className="text-danger" onClick={()=>void remove(row.id)}>Delete</button></td></tr>)}</tbody></table></div>
  </main></AdminGate>;
}
