import type { NextConfig } from "next";
import { realpathSync } from "node:fs";

const nextConfig: NextConfig = {
  turbopack: {
    root: realpathSync(process.cwd()),
  },
  allowedDevOrigins: [
    "192.168.3.6",
    "*.trycloudflare.com",
    "*.ngrok-free.app",
    "*.ngrok.io",
  ],
};

export default nextConfig;
