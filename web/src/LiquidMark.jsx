import { useEffect, useRef, useState } from "react";
import { liquidFragSource } from "./vendor/liquid-logo/liquid-frag";
import { parseLogoImage } from "./vendor/liquid-logo/parse-logo-image";

export default function LiquidMark({ motion }) {
  const canvas = useRef();
  const enabled = useRef(motion);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    enabled.current = motion;
  }, [motion]);
  useEffect(() => {
    const el = canvas.current;
    const gl = el.getContext("webgl2", { alpha: true, antialias: true });
    if (!gl) return;
    let disposed = false,
      frame = 0,
      program,
      texture,
      buffer;
    const shaders = [];
    function compile(type, src) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, src);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        gl.deleteShader(shader);
        throw new Error("Liquid mark shader unavailable");
      }
      shaders.push(shader);
      return shader;
    }
    parseLogoImage("/shield.svg")
      .then(({ imageData }) => {
        if (disposed) return;
        const vertex = compile(
          gl.VERTEX_SHADER,
          "#version 300 es\nin vec2 a_position;out vec2 vUv;void main(){vUv=.5*(a_position+1.);gl_Position=vec4(a_position,0.,1.);}",
        );
        const fragment = compile(gl.FRAGMENT_SHADER, liquidFragSource);
        program = gl.createProgram();
        gl.attachShader(program, vertex);
        gl.attachShader(program, fragment);
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS))
          throw new Error("Liquid mark unavailable");
        gl.useProgram(program);
        buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(
          gl.ARRAY_BUFFER,
          new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
          gl.STATIC_DRAW,
        );
        const position = gl.getAttribLocation(program, "a_position");
        gl.enableVertexAttribArray(position);
        gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
        texture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texImage2D(
          gl.TEXTURE_2D,
          0,
          gl.RGBA,
          imageData.width,
          imageData.height,
          0,
          gl.RGBA,
          gl.UNSIGNED_BYTE,
          imageData.data,
        );
        gl.uniform1i(gl.getUniformLocation(program, "u_image_texture"), 0);
        for (const [key, value] of Object.entries({
          u_ratio: 1,
          u_img_ratio: 1,
          u_patternScale: 2,
          u_refraction: 0.015,
          u_edge: 0.4,
          u_patternBlur: 0.08,
          u_liquid: 0.12,
        })) {
          gl.uniform1f(gl.getUniformLocation(program, key), value);
        }
        el.width = 128;
        el.height = 128;
        gl.viewport(0, 0, 128, 128);
        const time = gl.getUniformLocation(program, "u_time");
        let clock = 0,
          last = performance.now();
        function render(now) {
          if (disposed) return;
          const delta = now - last;
          last = now;
          if (enabled.current) clock += delta * 0.2;
          gl.uniform1f(time, clock);
          gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
          frame = requestAnimationFrame(render);
        }
        frame = requestAnimationFrame(render);
        setReady(true);
      })
      .catch(() => {
        if (!disposed) setReady(false);
      });
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      if (texture) gl.deleteTexture(texture);
      if (buffer) gl.deleteBuffer(buffer);
      if (program) gl.deleteProgram(program);
      shaders.forEach((s) => gl.deleteShader(s));
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, []);
  return (
    <span className="liquid-mark">
      <img src="/shield.svg" alt="" style={{ opacity: ready ? 0 : 1 }} />
      <canvas
        ref={canvas}
        aria-hidden="true"
        style={{ opacity: ready ? 1 : 0 }}
      />
    </span>
  );
}
