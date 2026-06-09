DROP TABLE IF EXISTS public."Пользователи" CASCADE;
CREATE TABLE IF NOT EXISTS public."Пользователи"
(
    "ID" SERIAL NOT NULL,
    "Логин" VARCHAR(50) NOT NULL,
    "Хэш пароля" VARCHAR(255) NOT NULL,
    "Дата создания" TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    "Роль" VARCHAR(20) DEFAULT 'user' NOT NULL,
    CONSTRAINT "Пользователи_pkey" PRIMARY KEY ("ID"),
    CONSTRAINT "Пользователи_логин_unique" UNIQUE ("Логин")
)
TABLESPACE pg_default;

ALTER TABLE IF EXISTS public."Пользователи"
    OWNER TO newuser;

DROP TABLE IF EXISTS public."ТЭЦ" CASCADE;
CREATE TABLE IF NOT EXISTS public."ТЭЦ"
(
    "ID" SERIAL NOT NULL,
    "Порядковый номер" INTEGER NOT NULL,
    "Название" VARCHAR(100) NOT NULL,
    "Мощность" INTEGER NOT NULL,
    "Расположение" VARCHAR(200) NOT NULL,
    "Координата X" INTEGER NOT NULL,
    "Координата Y" INTEGER NOT NULL,
    "ID пользователя" INTEGER NOT NULL,
    "Дата создания" TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    CONSTRAINT "ТЭЦ_pkey" PRIMARY KEY ("ID"),
    CONSTRAINT "ТЭЦ_порядковый_номер_check" CHECK ("Порядковый номер" >= 1),
    CONSTRAINT "ТЭЦ_мощность_check" CHECK ("Мощность" >= 100 AND "Мощность" <= 1000),
    CONSTRAINT "ТЭЦ_fk_пользователь" FOREIGN KEY ("ID пользователя")
        REFERENCES public."Пользователи" ("ID") MATCH SIMPLE
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT "unique_chp_name_per_user" UNIQUE ("Название", "ID пользователя")
)
TABLESPACE pg_default;

ALTER TABLE IF EXISTS public."ТЭЦ"
    OWNER TO newuser;

CREATE INDEX IF NOT EXISTS "idx_тэц_id_пользователя" ON public."ТЭЦ" ("ID пользователя");
CREATE INDEX IF NOT EXISTS "idx_тэц_порядковый_номер" ON public."ТЭЦ" ("Порядковый номер");

DROP TABLE IF EXISTS public."Дома" CASCADE;
CREATE TABLE IF NOT EXISTS public."Дома"
(
    "ID" SERIAL NOT NULL,
    "Название" VARCHAR(100) NOT NULL,
    "Тип" VARCHAR(20) NOT NULL,
    "ID ТЭЦ" INTEGER NOT NULL,
    "Температура" INTEGER NOT NULL,
    "Координата X" INTEGER NOT NULL,
    "Координата Y" INTEGER NOT NULL,
    "Дата создания" TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    CONSTRAINT "Дома_pkey" PRIMARY KEY ("ID"),
    CONSTRAINT "Дома_тип_check" CHECK ("Тип" IN ('apartment', 'private')),
    CONSTRAINT "Дома_температура_check" CHECK ("Температура" >= 40 AND "Температура" <= 95),
    CONSTRAINT "Дома_fk_ТЭЦ" FOREIGN KEY ("ID ТЭЦ")
        REFERENCES public."ТЭЦ" ("ID") MATCH SIMPLE
        ON UPDATE CASCADE
        ON DELETE CASCADE
)
TABLESPACE pg_default;

ALTER TABLE IF EXISTS public."Дома"
    OWNER TO newuser;

CREATE INDEX IF NOT EXISTS "idx_дома_id_тэц" ON public."Дома" ("ID ТЭЦ");

-- Функция для проверки уникальности названия дома в пределах пользователя
CREATE OR REPLACE FUNCTION check_unique_house_name_per_user()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public."Дома" d
        JOIN public."ТЭЦ" c ON d."ID ТЭЦ" = c."ID"
        WHERE d."Название" = NEW."Название"
        AND c."ID пользователя" = (SELECT "ID пользователя" FROM public."ТЭЦ" WHERE "ID" = NEW."ID ТЭЦ")
        AND d."ID" != COALESCE(NEW."ID", -1)
    ) THEN
        RAISE EXCEPTION 'Дом с таким названием уже существует у этого пользователя';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для проверки уникальности названия дома
DROP TRIGGER IF EXISTS trigger_unique_house_name ON public."Дома";
CREATE TRIGGER trigger_unique_house_name
    BEFORE INSERT OR UPDATE ON public."Дома"
    FOR EACH ROW
    EXECUTE FUNCTION check_unique_house_name_per_user();