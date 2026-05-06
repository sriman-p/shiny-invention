import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /**
   * Opening the app as http://127.0.0.1:3000 while the dev server binds to
   * localhost (or the reverse) is a different browser origin; Next blocks
   * dev-only WebSocket/HMR endpoints cross-origin by default, which yields
   * websocket handshake errors in the console.
   */
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
