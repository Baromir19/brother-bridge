

class LabelTemplateService:
    """
    Gestion CRUD des modèles d'étiquettes stockés dans la base de données.

    Toutes les opérations utilisent `id` (UUID) comme clé primaire.
    Le champ `name` reste unique mais n'est pas une clé primaire.
    """

    def __init__(self, label_repo: LabelRepository) -> None:
        self._repo = label_repo

    async def list(self) -> list[LabelTemplate]:
        rows = await self._repo.get_all()
        return [self._to_domain(r) for r in rows]

    async def get(self, label_id: int) -> LabelTemplate:
        """Raises: LabelTemplateNotFoundError si introuvable."""
        row = await self._repo.get_by_id(label_id)

        if row is None:
            raise LabelTemplateNotFoundError(label_id)

        return self._to_domain(row)

    async def create(self, data: LabelTemplate) -> LabelTemplate:
        """Raises: LabelAlreadyExistsException, LabelTemplateNotFoundError."""
        await self._assert_name_unique(data.name, exclude_id=None)
        self._require_file_exists(data.template)

        row = LabelTemplateORM(
            # id=data.id or str(uuid.uuid4()),
            name=data.name,
            template=data.template,
            fields=data.fields,
            description=data.description or None,
            is_active=True,
        )

        saved = await self._repo.create(row)
        return self._to_domain(saved)

    async def update(self, label_id: int, data: LabelTemplate) -> LabelTemplate:
        """Raises: LabelTemplateNotFoundError, LabelAlreadyExistsException."""
        row = await self._repo.get_by_id(label_id)
        if row is None:
            raise LabelTemplateNotFoundError(label_id)

        await self._assert_name_unique(data.name, exclude_id=label_id)
        self._require_file_exists(data.template)

        row.name = data.name
        row.template = data.template
        row.fields = data.fields
        row.description = data.description or None
        row.is_active = True

        saved = await self._repo.update(row)
        return self._to_domain(saved)

    async def delete(self, label_id: int) -> None:
        row = await self._repo.get_by_id(label_id)

        if row is None:
            raise LabelTemplateNotFoundError(label_id)

        await self._repo.delete(row)

    # private

    async def _assert_name_unique(self, name: str, exclude_id: int | None) -> None:
        all_rows = await self._repo.get_all()
        for row in all_rows:
            if row.name == name and row.id != exclude_id:
                raise LabelAlreadyExistsException(
                    f"Un modèle nommé '{name}' existe déjà"
                )

    def _require_file_exists(self, template: str) -> None:
        path = PRINTER_LABEL_DIR / template
        if not path.exists():
            raise LabelTemplateNotFoundError(
                f"Fichier .lbx introuvable : '{template}'. Uploadez-le d'abord."
            )

    @staticmethod
    def _to_domain(row: LabelTemplateORM) -> LabelTemplate:
        return LabelTemplate(
            id=row.id,
            name=row.name,
            template=row.template,
            fields=row.fields,
            description=row.description or "",
            is_active=row.is_active,
        )
