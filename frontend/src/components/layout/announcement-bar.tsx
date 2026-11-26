"use client";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api/client";
export function AnnouncementBar(){const [text,setText]=useState("");useEffect(()=>{void apiRequest<Record<string,{body:string;enabled:boolean}>>("/content").then(data=>{const item=data.announcement;if(item?.enabled)setText(item.body);}).catch(()=>undefined);},[]);return text?<div className="bg-ink px-4 py-2 text-center text-xs font-medium text-paper" role="status">{text}</div>:null;}
