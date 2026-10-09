import os
import uuid
from typing import Dict, Any, Tuple
from PIL import Image
import pypdfium2 as pdfium
from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.core.logging import logger


class DocumentService:
    @staticmethod
    def validate_file(file: UploadFile) -> Tuple[str, str]:
        """
        Validates file existence, extension, and content type.
        Returns (filename, extension).
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

        filename = file.filename
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '.{ext}'. Supported formats: {', '.join(settings.ALLOWED_EXTENSIONS)}",
            )

        return filename, ext

    @staticmethod
    async def save_uploaded_file(file: UploadFile, project_id: str) -> Dict[str, Any]:
        """
        Saves raw uploaded file and prepares a standardized PNG representation for vision and display.
        """
        filename, ext = DocumentService.validate_file(file)

        # Read file bytes to validate size and non-emptiness
        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")

        if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {max_mb:.0f} MB.",
            )

        # Unique destination path
        project_upload_dir = os.path.join(settings.UPLOAD_DIR, project_id)
        os.makedirs(project_upload_dir, exist_ok=True)

        raw_file_path = os.path.join(project_upload_dir, f"original_{uuid.uuid4().hex[:8]}.{ext}")
        with open(raw_file_path, "wb") as f:
            f.write(content)

        # Prepare normalized display image path (PNG)
        display_image_path = os.path.join(project_upload_dir, "display_plan.png")
        width = 1200
        height = 900

        try:
            if ext == "pdf":
                logger.info(f"Extracting first page from architectural PDF: {filename}")
                pdf = pdfium.PdfDocument(raw_file_path)
                if len(pdf) == 0:
                    raise HTTPException(status_code=400, detail="The uploaded PDF contains no pages.")

                page = pdf[0]
                # Render page at 2x scale (144 DPI) for clarity
                image = page.render(scale=2.0).to_pil()
                width, height = image.size
                image.save(display_image_path, format="PNG")
                pdf.close()
            else:
                # Direct raster image
                logger.info(f"Validating architectural image: {filename}")
                with Image.open(raw_file_path) as img:
                    img.verify()

                # Re-open for conversion & dimension reading
                with Image.open(raw_file_path) as img:
                    width, height = img.size
                    rgb_img = img.convert("RGB")
                    rgb_img.save(display_image_path, format="PNG")

        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"Failed to process plan document: {e}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail=f"Could not read floor plan drawing. File may be corrupted or unreadable. Error: {str(e)}",
            )

        return {
            "filename": filename,
            "raw_file_path": raw_file_path,
            "display_image_path": display_image_path,
            "content_type": file.content_type or f"image/{ext}",
            "size": file_size,
            "width": width,
            "height": height,
        }
