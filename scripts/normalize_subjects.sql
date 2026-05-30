-- v0.28 数据治理 · 统一 subject 命名 chinese → 语文
UPDATE knowledge_points SET subject='语文' WHERE subject='chinese';
UPDATE document_embeddings
SET doc_metadata = jsonb_set(doc_metadata, '{subject}', '"语文"'::jsonb)
WHERE doc_metadata->>'subject' = 'chinese';
SELECT subject, count(*) FROM knowledge_points GROUP BY subject ORDER BY 2 DESC;
