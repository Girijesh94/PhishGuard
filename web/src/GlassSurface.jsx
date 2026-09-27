import { useEffect, useRef } from "react";
import Container from "./vendor/liquid-glass/container";

class Surface extends Container {
  // Sample only the decorative scene, never user inputs or page content.
  init() {
    this.createElement();
    this.setupCanvas();
  }
}
export default function GlassSurface() {
  const host = useRef();
  useEffect(() => {
    const holder = host.current;
    let surface,
      disposed = false,
      timer,
      frame;
    function capture() {
      if (disposed) return;
      const snapshot = document.createElement("canvas");
      snapshot.width = window.innerWidth;
      snapshot.height = window.innerHeight;
      const ctx = snapshot.getContext("2d");
      const gradient = ctx.createLinearGradient(
        0,
        0,
        snapshot.width,
        snapshot.height,
      );
      gradient.addColorStop(0, "#e4eaf8");
      gradient.addColorStop(0.65, "#9eadde");
      gradient.addColorStop(1, "#e3eefc");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, snapshot.width, snapshot.height);
      document
        .querySelectorAll(".gradient-backdrop canvas,.shield-scene canvas")
        .forEach((canvas) => {
          const rect = canvas.getBoundingClientRect();
          try {
            ctx.drawImage(canvas, rect.left, rect.top, rect.width, rect.height);
          } catch {}
        });
      if (!surface) {
        surface = new Surface({ borderRadius: 20, tintOpacity: 0.1 });
        if (!surface.gl) {
          surface.element.remove();
          surface = null;
          return;
        }
        holder.appendChild(surface.element);
        surface.element.style.cssText =
          "position:absolute;inset:0;isolation:isolate;";
        surface.canvas.style.zIndex = "0";
        surface.canvas.style.boxShadow = "none";
      }
      surface.updateSizeFromDOM();
      frame = requestAnimationFrame(() => {
        if (disposed) return;
        if (!surface.webglInitialized) {
          surface.setupShader(snapshot);
          surface.webglInitialized = true;
        } else {
          const r = surface.gl_refs;
          r.gl.bindTexture(r.gl.TEXTURE_2D, r.texture);
          r.gl.texImage2D(
            r.gl.TEXTURE_2D,
            0,
            r.gl.RGBA,
            r.gl.RGBA,
            r.gl.UNSIGNED_BYTE,
            snapshot,
          );
          r.gl.uniform2f(r.textureSizeLoc, snapshot.width, snapshot.height);
          surface.render?.();
        }
      });
    }
    timer = setTimeout(capture, 1500);
    const resize = () => {
      clearTimeout(timer);
      timer = setTimeout(capture, 250);
    };
    window.addEventListener("resize", resize);
    return () => {
      disposed = true;
      clearTimeout(timer);
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      if (surface) {
        window.removeEventListener("scroll", surface._scrollHandler);
        surface.gl?.getExtension("WEBGL_lose_context")?.loseContext();
        Container.instances = Container.instances.filter((i) => i !== surface);
        surface.element.remove();
      }
    };
  }, []);
  return <span ref={host} className="glass-surface" aria-hidden="true" />;
}
