require "./spec_helper"

describe MassStorageManager do
  it "accepts only safe raw image filenames" do
    MassStorageManager.valid_filename?("rescue-1.0.img").should be_true
    ["../secret.img", "/etc/passwd.img", "nested/file.img", ".hidden.img",
     "a'quote.img", "a<script>.img", "a.img\n", "a.iso", "a" * 180 + ".img"].each do |name|
      MassStorageManager.valid_filename?(name).should be_false
    end
  end

  it "rejects traversal and symlink selection and deletion" do
    previous = Dir.current
    temp = File.tempname("kv-storage-test", nil)
    Dir.mkdir(temp, 0o700)
    begin
      Dir.cd(temp)
      storage = MassStorageManager.new
      root = MassStorageManager.storage_dir
      File.write("outside.img", "private")
      File.write(File.join(root, "safe.img"), "disk")
      File.symlink(File.expand_path("outside.img"), File.join(root, "link.img"))
      MassStorageManager.image_path("safe.img").should eq(File.join(root, "safe.img"))
      MassStorageManager.image_path("../outside.img").should be_nil
      MassStorageManager.image_path("link.img").should be_nil
      storage.select_image("safe.img")[:success].should be_true
      storage.delete_image("safe.img")[:success].should be_false
      storage.select_image("../outside.img")[:success].should be_false
      storage.delete_image("../outside.img")[:success].should be_false
      storage.select_image("link.img")[:success].should be_false
      storage.delete_image("link.img")[:success].should be_false
      storage.select_image(nil)[:success].should be_true
      storage.delete_image("safe.img")[:success].should be_true
      File.read("outside.img").should eq("private")
    ensure
      Dir.cd(previous)
      FileUtils.rm_rf(temp)
    end
  end
end

describe KVSecurity do
  it "bounds JSON input before parsing" do
    KVSecurity.read_json_body(IO::Memory.new("{}")).should eq("{}")
    expect_raises(Exception, "Request body too large") do
      KVSecurity.read_json_body(IO::Memory.new("x" * (KVSecurity::MAX_JSON_BYTES + 1)))
    end
  end
end
