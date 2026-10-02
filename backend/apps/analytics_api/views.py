from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsFacilityManager

from . import services
from .models import ImportKind

MAX_BYTES = 2 * 1024 * 1024


class ImportSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ImportKind.choices)
    dry_run = serializers.BooleanField(default=True)
    file = serializers.FileField()

    def validate_file(self, value):
        if value.size > MAX_BYTES:
            raise serializers.ValidationError("The file is larger than 2 MB.")
        return value


class ImportView(APIView):
    """Bulk CSV import with a dry run and a per-row error report (FR-40); facility managers only."""

    permission_classes = [IsFacilityManager]
    parser_classes = [MultiPartParser]

    def post(self, request):
        data = ImportSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            batch = services.run_import(request.user, v["kind"], v["file"].read(), v["dry_run"])
        except services.ImportRefused as exc:
            raise ValidationError({"file": str(exc)}) from exc
        return Response(
            {
                "batch_id": batch.pk,
                "dry_run": batch.dry_run,
                "rows_total": batch.rows_total,
                "rows_rejected": batch.rows_rejected,
                "errors": list(
                    batch.errors.order_by("row_index").values("row_index", "defect_code", "message")
                ),
            },
            status=status.HTTP_201_CREATED,
        )
