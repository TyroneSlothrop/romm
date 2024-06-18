import os
import shutil
from pathlib import Path

import requests
from config import RESOURCES_BASE_PATH
from fastapi import HTTPException, status
from logger.logger import log
from PIL import Image
from urllib3.exceptions import ProtocolError

from .base_handler import CoverSize, FSHandler


class FSResourcesHandler(FSHandler):
    def __init__(self) -> None:
        pass

    @staticmethod
    def _cover_exists(platform_id: int, rom_id: int, size: CoverSize):
        """Check if rom cover exists in filesystem

        Args:
            fs_slug: short name of the platform
            rom_name: name of rom file
            size: size of the cover
        Returns
            True if cover exists in filesystem else False
        """
        return bool(
            os.path.exists(
                f"{RESOURCES_BASE_PATH}/{platform_id}/{rom_id}/cover/{size.value}.png"
            )
        )

    @staticmethod
    def resize_cover_to_small(cover_path: str):
        """Path of the cover image to resize"""
        cover = Image.open(cover_path)
        small_width = int(cover.width * 0.1)
        small_height = int(cover.height * 0.1)
        small_size = (small_width, small_height)
        small_img = cover.resize(small_size)
        small_img.save(cover_path)

    def _store_cover(
        self, platform_id: int, rom_id: int, url_cover: str, size: CoverSize
    ):
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            rom_name: name of rom file
            url_cover: url to get the cover
            size: size of the cover
        """
        cover_file = f"{size.value}.png"
        cover_path = f"{RESOURCES_BASE_PATH}/{platform_id}/{rom_id}/cover"

        try:
            res = requests.get(
                (
                    url_cover.replace("t_thumb", "t_cover_small").replace(
                        "t_cover_big", "t_cover_small"
                    )
                    if size.value == CoverSize.SMALL.value
                    else url_cover.replace("t_thumb", "t_1080p").replace(
                        "t_cover_big", "t_1080p"
                    )
                ),
                stream=True,
                timeout=120,
            )
        except requests.exceptions.ConnectionError as exc:
            log.critical("Connection error: can't connect to IGDB")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to IGDB, check your internet connection.",
            ) from exc

        if res.status_code == 200:
            Path(cover_path).mkdir(parents=True, exist_ok=True)
            with open(f"{cover_path}/{cover_file}", "wb") as f:
                shutil.copyfileobj(res.raw, f)
            if size == CoverSize.SMALL:
                self.resize_cover_to_small(f"{cover_path}/{cover_file}")

    @staticmethod
    def _get_cover_path(platform_id: int, rom_id: int, size: CoverSize):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom file
            size: size of the cover
        """
        return f"{platform_id}/{rom_id}/cover/{size.value}.png"

    def get_rom_cover(
        self, overwrite: bool, platform_id: int, rom_id: int, url_cover: str = ""
    ) -> tuple[str, str]:
        if (
            overwrite or not self._cover_exists(platform_id, rom_id, CoverSize.SMALL)
        ) and url_cover:
            self._store_cover(platform_id, rom_id, url_cover, CoverSize.SMALL)
        path_cover_s = (
            self._get_cover_path(platform_id, rom_id, CoverSize.SMALL)
            if self._cover_exists(platform_id, rom_id, CoverSize.SMALL)
            else ""
        )

        if (
            overwrite or not self._cover_exists(platform_id, rom_id, CoverSize.BIG)
        ) and url_cover:
            self._store_cover(platform_id, rom_id, url_cover, CoverSize.BIG)
        path_cover_l = (
            self._get_cover_path(platform_id, rom_id, CoverSize.BIG)
            if self._cover_exists(platform_id, rom_id, CoverSize.BIG)
            else ""
        )

        return path_cover_s, path_cover_l

    @staticmethod
    def remove_cover(
        rom_id: int,
        platform_id: int,
    ):
        try:
            cover_path = os.path.join(
                RESOURCES_BASE_PATH, str(platform_id), str(rom_id), "cover"
            )
            shutil.rmtree(cover_path)
        except FileNotFoundError:
            log.warning(f"Couldn't remove {rom_id} cover. {cover_path} doesn't exists.")
        return {"path_cover_s": "", "path_cover_l": ""}

    @staticmethod
    def build_artwork_path(rom_id: int, platform_id: int, file_ext: str):
        path_cover_l = f"{platform_id}/{rom_id}/cover/{CoverSize.BIG.value}.{file_ext}"
        path_cover_s = (
            f"{platform_id}/{rom_id}/cover/{CoverSize.SMALL.value}.{file_ext}"
        )
        artwork_path = f"{RESOURCES_BASE_PATH}/{platform_id}/{rom_id}/cover"
        Path(artwork_path).mkdir(parents=True, exist_ok=True)
        return path_cover_l, path_cover_s, artwork_path

    @staticmethod
    def _store_screenshot(platform_id: int, rom_id: int, url: str, idx: int):
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            url: url to get the screenshot
        """
        screenshot_file = f"{idx}.jpg"
        screenshot_path = f"{RESOURCES_BASE_PATH}/{platform_id}/{rom_id}/screenshots"

        try:
            res = requests.get(url, stream=True, timeout=120)
        except requests.exceptions.ConnectionError as exc:
            log.critical("Connection error: can't connect to IGDB")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to IGDB, check your internet connection.",
            ) from exc

        if res.status_code == 200:
            Path(screenshot_path).mkdir(parents=True, exist_ok=True)
            with open(f"{screenshot_path}/{screenshot_file}", "wb") as f:
                try:
                    shutil.copyfileobj(res.raw, f)
                except ProtocolError:
                    log.warning(
                        f"Failure writing screenshot {url} to file (ProtocolError)"
                    )

    @staticmethod
    def _get_screenshot_path(platform_id: int, rom_id: int, idx: str):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            idx: index number of screenshot
        """
        return f"{platform_id}/{rom_id}/screenshots/{idx}.jpg"

    def get_rom_screenshots(
        self, platform_id: int, rom_id: int, url_screenshots: list
    ) -> list[str]:
        path_screenshots: list[str] = []
        for idx, url in enumerate(url_screenshots):
            self._store_screenshot(platform_id, rom_id, url, idx)
            path_screenshots.append(
                self._get_screenshot_path(platform_id, rom_id, str(idx))
            )
        return path_screenshots
