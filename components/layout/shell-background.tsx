export function ShellBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-[linear-gradient(135deg,oklch(0.99_0.006_170)_0%,oklch(0.975_0.018_180)_45%,oklch(0.985_0.012_260)_100%)]" />
      <div className="absolute -left-24 top-16 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
      <div className="absolute right-[-10rem] top-1/3 h-96 w-96 rounded-full bg-violet-400/8 blur-3xl" />
      <div className="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-sky-300/8 blur-3xl" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,oklch(0.62_0.04_210_/_8%)_1px,transparent_0)] bg-[length:28px_28px] [mask-image:linear-gradient(to_bottom,black,transparent_72%)]" />
    </div>
  );
}

