-- movie_app_lab의 movies/reviews가 비어 있을 때만 적용한다.
BEGIN;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM movies) OR EXISTS (SELECT 1 FROM reviews) THEN
    RAISE EXCEPTION '기존 데이터가 있습니다. 삭제하거나 중복 입력하지 않습니다.';
  END IF;
END $$;

INSERT INTO movies (
  movie_id, movie_title, release_year, source, registered_at, updated_at
)
SELECT 'backup-lab-movie-' || n, '복구 검증 영화 ' || n, 2026,
       'backup-lab', TIMESTAMP '2026-10-19 00:00:00',
       TIMESTAMP '2026-10-19 00:00:00'
FROM generate_series(1, 100) AS n;

INSERT INTO reviews (
  review_id, movie_id, text, source, external_review_id,
  author, rating, collected_at, is_processed
)
SELECT 'backup-lab-review-' || n,
       'backup-lab-movie-' || (((n - 1) % 100) + 1),
       '실제 앱 테이블 복구 검증용 리뷰 ' || n,
       'backup-lab', n::text, '테스트 사용자', ((n - 1) % 5) + 1,
       TIMESTAMP '2026-10-19 00:00:00', false
FROM generate_series(1, 10000) AS n;
COMMIT;

SELECT 'movies' AS table_name, count(*) FROM movies
UNION ALL SELECT 'reviews', count(*) FROM reviews;
