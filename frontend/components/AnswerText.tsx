export function AnswerText({ text }: { text: string }) {
  const paragraphs = text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

  if (paragraphs.length === 0) {
    return <p className="italic text-text-secondary">No answer was produced.</p>;
  }

  return (
    <div className="flex flex-col gap-3 text-[15px] leading-relaxed text-text-primary">
      {paragraphs.map((paragraph, index) => (
        <p key={index}>{paragraph}</p>
      ))}
    </div>
  );
}
