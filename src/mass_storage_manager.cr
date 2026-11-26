# Mass Storage Manager for KVM system (new model)
class MassStorageManager
  Log = ::Log.for(self)

  @selected_image : String? = nil

  MAX_UPLOAD_BYTES = 1_073_741_824_i64
  MAX_IMAGE_BYTES = 8_589_934_592_i64

  def self.valid_filename?(filename : String) : Bool
    filename.bytesize <= 180 && !!(filename =~ /\A[A-Za-z0-9][A-Za-z0-9._-]*\.img\z/)
  end

  def self.storage_dir : String
    path = File.expand_path("disk-images")
    Dir.mkdir(path, 0o700) unless Dir.exists?(path)
    raise "Unsafe disk image directory" unless File.real_path(path) == path
    path
  end

  def self.image_path(filename : String) : String?
    return nil unless valid_filename?(filename)
    path = File.join(storage_dir, filename)
    return nil unless File.file?(path) && !File.symlink?(path)
    return nil unless File.real_path(path) == path
    path
  end

  def available_images
    Dir.children(self.class.storage_dir).compact_map { |name| self.class.image_path(name) }
  end

  def delete_image(filename : String)
    unless full_path = self.class.image_path(filename)
      return {success: false, message: "Image not found"}
    end
    if @selected_image == full_path
      return {success: false, message: "Cannot delete selected image"}
    end
    File.delete(full_path)
    {success: true, message: "Image deleted successfully"}
  rescue ex
    Log.error { "Image deletion failed (#{ex.class})" }
    {success: false, message: "Failed to delete image"}
  end

  # Accept only a validated image name, not a client-supplied filesystem path.
  def select_image(filename : String?)
    if filename
      path = self.class.image_path(filename)
      return {success: false, message: "Invalid or missing disk image"} unless path
      @selected_image = path
    else
      @selected_image = nil
    end
    {success: true, selected: @selected_image.try { |path| File.basename(path) }}
  rescue ex
    Log.error { "Image selection failed (#{ex.class})" }
    {success: false, message: "Failed to select image"}
  end

  # Return the currently selected image
  def selected_image
    @selected_image
  end

  # Status for API
  def status
    {
      selected_image:   @selected_image,
      available_images: available_images,
    }
  end

  # Returns a hash with the actual mass storage status from the system, not just internal state
  def actual_status
    base = "/sys/kernel/config/usb_gadget/odroidc2_composite/functions/mass_storage.0"
    exists = Dir.exists?(base)
    file = nil
    ro = nil
    attached = false
    if exists
      file_file = File.join(base, "lun.0/file")
      ro_file = File.join(base, "lun.0/ro")
      if File.exists?(file_file)
        file = File.read(file_file).strip
        attached = !file.empty?
      end
      if File.exists?(ro_file)
        ro = File.read(ro_file).strip == "1"
      end
    end
    {
      exists:         exists,
      attached:       attached,
      file:           file,
      ro:             ro,
      configured:     !@selected_image.nil?,
      selected_image: @selected_image,
    }
  end

  def cleanup
    @selected_image = nil
  end
end
